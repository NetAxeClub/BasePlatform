#!/usr/bin/python
# _*_coding:utf-8 _*_

import json
import redis
from confload.confload import config


class RedisOps:
    def __init__(self):
        self.pool = redis.ConnectionPool(host=config.redis_host, port=int(config.redis_port), db=11,
                                         password=config.redis_pwd or None, decode_responses=True)
        self.redis_conn = redis.StrictRedis(connection_pool=self.pool)
        self.r = self.redis_conn.pubsub()

    def get_all(self):
        res = redis.StrictRedis(connection_pool=self.pool)
        keys = res.keys()
        return keys

    def zadd(self, key, value, score):
        """
        :param key:
        :param value:
        :param score:
        :return:
        """
        self.redis_conn.zadd(key, mapping={value: score})

    def zcount(self, key, start, end):
        """
        """
        return self.redis_conn.zcount(key, start, end)

    def zrangebyscore(self, key, start, end):
        """
        :param key:
        :param value:
        :param score:
        :return:
        """
        return self.redis_conn.zrangebyscore(key, start, end, start=None, num=None,
                                             withscores=True, score_cast_func=float)

    def zrange(self, key, start, end):
        """
        :param key:
        :param value:
        :param score:
        :return:
        """
        return self.redis_conn.zrange(key, start, end, desc=False, withscores=True,
                                      score_cast_func=float)

    def zrembyscore(self, key, start, end):
        return self.redis_conn.zremrangebyscore(key, start, end)

    def lpush(self, rediskey, *values):
        """
        在rediskey对应的list中添加元素每个新的元素都添加到列表的头部
        :param rediskey:
        :return:
        """
        return self.redis_conn.lpush(rediskey, *values)

    def lpop(self, rediskey):
        """
        移除并返回列表的第一个元素
        :param rediskey:
        :return:
        """
        return self.redis_conn.lpop(rediskey)

    def rpush(self, rediskey, *values):
        """
        在rediskey对应的list中添加元素每个新的元素都添加到列表的尾部
        :param rediskey:
        :return:
        """
        self.redis_conn.rpush(rediskey, *values)

    def rpop(self, rediskey):
        """
        移除并返回列表的最后一个元素
        :param rediskey:
        :return:
        """
        return self.redis_conn.rpop(rediskey)

    def lrange(self, rediskey):
        """
        获取列表中所有数据
        :param rediskey:
        :return:
        """
        return self.redis_conn.lrange(rediskey, 0, -1)

    def delete(self, *args):
        return self.redis_conn.delete(*args)

    def set(self, rediskey, value, ex=None, px=None):
        return self.redis_conn.set(rediskey, value, ex, px)

    def mset(self, **kwargs):
        return self.redis_conn.mset(**kwargs)

    def get(self, rediskey):
        return self.redis_conn.get(rediskey)

    def mget(self, *args):
        return self.redis_conn.mget(*args)

    def sadd(self, rediskey, *values):
        return self.redis_conn.sadd(rediskey, *values)

    def smembers(self, rediskey):
        return self.redis_conn.smembers(rediskey)

    def publish(self, channel, message):
        """
        在指定频道上发布消息
        :param msg:
        :return:
        """
        self.redis_conn.publish(channel, message)

    def subscribe(self, channel, *args, **kwargs):
        self.r.subscribe(channel, *args, **kwargs)
        return self.r.listen()

    def unsubscribe(self, channel):
        self.r.unsubscribe(channel)

    def sub_message(self, channel):
        self.r.subscribe(channel)
        return self.r.get_message(ignore_subscribe_messages=True)


class RedisHelper(RedisOps):

    def __init__(self, chan: str):
        super(RedisHelper, self).__init__()
        # 频道名称
        self.chan = chan

    # def publish(self, msg):
    #     """
    #     在指定频道上发布消息
    #     :param msg:
    #     :return:
    #     """
    #     # publish(): 在指定频道上发布消息，返回订阅者的数量
    #     self.__conn.publish(self.chan, msg)
    #     return True
    #
    # def subscribe(self):
    #     # 返回发布订阅对象，通过这个对象你能1）订阅频道 2）监听频道中的消息
    #     # _pub = self.__conn.publish()
    #     # 订阅某个频道，与publish()中指定的频道一样。消息会发布到这个频道中
    #     _pub = self.__conn.subscribe(self.chan)
    #     return _pub


RedisChannel = RedisHelper('msg_gateway')


# 消息发布
def test_pub(name):
    data = {
        "type": name,
        "msgtype": "text",
        "body": {
            "user": 17755153438,
            "title": "",
            "img_id": "",
            "digest": "",
            "content": "测试。。。。。。。。",
        }
    }
    RedisChannel.publish(json.dumps(data))


# 消息订阅
def test_sub():
    redis_sub = RedisChannel.subscribe()
    for i in redis_sub.listen():
        print(i)


if __name__ == '__main__':
    test_pub("sms")
