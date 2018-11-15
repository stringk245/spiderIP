#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
__title__ = ''
__author__ = 'stringk'
__mtime__ = '2018/6/25'
# qq:2456056533

佛祖保佑  永无bug!

"""
# grequests 内部做了处理
# import gevent
# from gevent import monkey
#
# monkey.patch_all()

import grequests        # grequests比较老的库了,gevent  win10使用一堆毛病
import asyncio
import aiohttp
from threading import Thread

import functools
import requests
import random


http_url = ['http://news.163.com/latest/', 'http://fanyi.youdao.com/','http://news.qq.com/','http://vdisk.weibo.com/','http://www.kugou.com/']
https_url =['https://www.baidu.com/','https://fanyi.baidu.com/','https://news.baidu.com/','https://www.toutiao.com/','https://www.sogou.com/','https://www.xunlei.com/','https://www.csdn.net/']

class IPCheck:

    def check_ip(self, queue, new_queue):

        aiohttp_tasks = []
        grequests_tasks = []
        semaphore = asyncio.Semaphore(300)
        while True:
            if queue.empty(): break
            item = queue.get(timeout=0.5)
            protocol = item['protocol']
            ip = item['ip']
            proxy = {protocol:ip}  # {'http': 'http://101.236.36.31:8866'}

            # 区分http 和 https
            if 'http' in proxy.keys():
                # 模式1: 最快,但是会超过最大并发数
                # task = asyncio.ensure_future(self.aiohttp_check(proxy,random.choice(http_url)))

                # 模式2: 解决最大并发数问题，限制并发
                task = asyncio.ensure_future(self.aiohttp_check2(proxy,random.choice(http_url),semaphore))

                # 任务数组
                task.add_done_callback(functools.partial(self.aiohttp_callback, new_queue=new_queue, item=item))
                aiohttp_tasks.append(task)

                '''
                # 模式3: 使用grequests框架,不使用asyncio,不用考虑最大并发数问题
                
                grequests_tasks.append(grequests.get(random.choice(http_url), proxies=proxy,callback=functools.partial(self.grequests_callback,new_queue=new_queue, item=item), timeout=1))

                '''
            else:
                # grequests 校验https
                grequests_tasks.append(grequests.get(random.choice(https_url), proxies=proxy,
                                                     callback=functools.partial(self.grequests_callback,new_queue=new_queue, item=item), timeout=2))



        return aiohttp_tasks, grequests_tasks

    # async def aiohttp_check(self, proxy,url):
    #     '''
    #     aiohttp 请求: aiohttp 不支持 https 代理！
    #     :param proxy:
    #     :return:
    #     '''
    #     proxies = proxy['http']
    #     async with aiohttp.ClientSession() as session:
    #         try:
    #             async with session.get(url, proxy=proxies, timeout=1.5) as resp:  # proxy =  http:// 218.60.8.98:3129
    #                 return resp.status
    #         except Exception as e:
    #             return None

    async def aiohttp_check2(self, proxy,url, semaphore):
        '''
         解决: 超过最大连接数报 too many file descriptors in select()
        :param proxy: 
        :param semaphore: 
        :return: 
        '''
        proxies = proxy['http']
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(url, proxy=proxies, timeout=2) as resp:  # aiohttp_proxy =  http:// 218.60.8.98:3129
                        return resp.status
                except Exception as e:

                    return None

    def aiohttp_callback(self, future, new_queue, item):
        '''
        aiohttp 请求回调函数
        :param future: 
        :param new_queue: 
        :param item: 
        :return: 
        '''
        status = future.result()
        if status == 200:
            print('******************************可用的ip:', item)
            new_queue.put(item)

    def run_aiohttp(self, loop, aiohttp_tasks):
        '''
         loop 执行 aiohttp
        :param loop: 
        :param aiohttp_tasks: 
        :return: 
        '''
        if aiohttp_tasks:
            loop.run_until_complete(asyncio.wait(aiohttp_tasks))

    def run_grequests(self, grequests_tasks):
        '''
        执行 grequests
        :param grequests_tasks: 
        :return: 
        '''
        if grequests_tasks:
            grequests.map(grequests_tasks,)


    def grequests_callback(self, resp, new_queue, item, *args, **kwargs):
        '''
        grequests 回调函数
        :param resp: 
        :param new_queue: 
        :param item: 
        :param args: 
        :param kwargs: 
        :return: 
        '''

        if resp.status_code == 200:
            print('******************************可用的ip:', item)
            new_queue.put(item)

    def run_ip_check(self, loop, queue, new_queue):
        '''
        返回线程组：开启两个线程,分别执行 aiohttp 请求(针对http协议) 和 grequests 请求(针对https协议)
        :param loop: aiohttp 执行loop
        :param queue: 爬虫爬到的item
        :param new_queue: 校验ip后的item
        :return:
        '''
        aiohttp_tasks, grequests_tasks = self.check_ip(queue, new_queue)
        thread1 = Thread(target=self.run_aiohttp, args=(loop, aiohttp_tasks))
        thread2 = Thread(target=self.run_grequests, args=(grequests_tasks,))

        for t in [thread1, thread2]:
            t.setDaemon(True)
            t.start()

        for t in [thread1, thread2]:
            t.join()



class IPcheckRedis(IPCheck):
    '''
    另一种实现校验 失败 ：通过redis, 在 redis sadd()操作时候 报  greenlet.error: cannot switch to a different thread, 两个线程同时添加redis导致，maybe
    '''

    def check_ip(self, redis,redis_key,redis_key2):
        aiohttp_tasks = []
        grequests_tasks = []
        semaphore = asyncio.Semaphore(300)
        while True:
            item = redis.spop(redis_key)
            if not item: break
            _item = eval(item.decode('utf-8'))
            protocol = _item['protocol']
            ip = _item['ip']
            proxy = {protocol:ip}  # {'http': 'http://101.236.36.31:8866'}

            if 'http' in proxy.keys():
                # 模式1: 最快,但是会超过最大并发数
                # task = asyncio.ensure_future(self.aiohttp_check(proxy,random.choice(http_url)))

                # 模式2: 解决最大并发数问题，限制并发
                task = asyncio.ensure_future(self.aiohttp_check2(proxy, random.choice(http_url),semaphore))

                # 任务数组
                task.add_done_callback(functools.partial(self.aiohttp_callback, redis=redis,redis_key=redis_key2, item=_item))
                aiohttp_tasks.append(task)

                '''
                # 模式3: 使用grequests框架,不使用asyncio,不用考虑最大并发数问题
                grequests_tasks.append(grequests.get(random.choice(http_url), proxies=proxy,callback=functools.partial(self.grequests_callback,new_queue=new_queue, item=item), timeout=1))

                '''
            else:
                grequests_tasks.append(grequests.get(random.choice(https_url), proxies=proxy,
                                                     callback=functools.partial(self.grequests_callback,
                                                                                redis=redis,redis_key=redis_key2, item=_item),timeout=1.5))

        return aiohttp_tasks, grequests_tasks


    def aiohttp_callback(self, future, redis,redis_key, item):
        '''
        aiohttp 请求回调函数

        '''
        status = future.result()
        if status == 200:
            print('******************************可用的ip:', item)
            redis.sadd(redis_key,item)
            # redis.lpush(redis_key,item)



    def grequests_callback(self, resp, redis,redis_key, item, *args, **kwargs):
        '''
        grequests 回调函数

        '''

        if resp.status_code == 200:
            print('******************************可用的ip:', item)
            redis.sadd(redis_key, item)
            # redis.lpush(redis_key, item)



    def run_ip_check(self,loop,redis,redis_key,redis_key2):
        '''
        返回线程组：开启两个线程,分别执行 aiohttp 请求(针对http协议) 和 grequests 请求(针对https协议)
        '''
        aiohttp_tasks, grequests_tasks = self.check_ip(redis, redis_key,redis_key2)
        thread3 = Thread(target=self.run_aiohttp, args=(loop, aiohttp_tasks))
        thread4 = Thread(target=self.run_grequests, args=(grequests_tasks,))

        for t in [thread3,thread4]:
            t.setDaemon(True)
            t.start()

        for t in [thread3,thread4]:
            t.join()



def single_request():
    '''
    单个 ip 测试
    :return:
    '''
    url = 'http://news.163.com/latest/'
    proxies = {'http': 'http://117.21.182.14:80'}

    # url = 'https://www.baidu.com/'
    # proxies = {'https': 'https://119.27.177.169:80'}

    try:
        resp = requests.get(url, proxies=proxies, timeout=1)
        print(resp.status_code)
    except Exception as e:
        print(e)



if __name__ == '__main__':
    single_request()
