# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      db_sync
   Description:
   Author:          Lijiamin
   date：           2023/4/4 11:05
-------------------------------------------------
   Change Activity:
                    2023/4/4 11:05
-------------------------------------------------
结合上面已有的代码封装一个MongoOps类，具备数据插入、更新、删除、以及针对索引的CRUD功能
"""
import pymongo
from confload.confload import config


client = pymongo.MongoClient(config.mongodb_url, connect=False)
db = client[config.project_name]

__all__ = ["SyncMongoOps"]


class SyncMongoOps:
    def __init__(self, collection_name):
        self.collection = db[collection_name]

    def insert(self, data):
        self.collection.insert_one(data)

    def update(self, query, data):
        self.collection.update_one(query, {"$set": data})

    def delete(self, query):
        self.collection.delete_one(query)

    def create_index(self, index):
        self.collection.create_index(index)

    def read(self, query):
        return self.collection.find(query)


