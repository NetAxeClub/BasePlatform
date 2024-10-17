# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      db_driver
   Description:
   Author:          Lijiamin
   date：           2023/4/4 10:33
-------------------------------------------------
   Change Activity:
                    2023/4/4 10:33
-------------------------------------------------
https://motor.readthedocs.io/en/stable/examples/index.html
https://github.com/mongodb-developer/mongodb-with-fastapi
"""
import motor.motor_asyncio
from bson import ObjectId
from backend.confload.confload import config

client = motor.motor_asyncio.AsyncIOMotorClient(config.mongodb_url)
db = client[config.project_name]


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class AsyncMongoOps:

    def __init__(self, collection_name: str):
        self.collection = db[collection_name]

    async def insert_data(self, data: dict):
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def update(self, query, data):
        result = await self.collection.update_one(query, {"$set": data})
        return result.modified_count

    async def delete_data(self, id: str):
        result = self.collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count

    async def find(self, query_dict=None, fields=None, sort=None, limit=None, skip=None):
        if query_dict and fields and limit and skip:
            r = self.collection.find(query_dict, fields).limit(limit).skip(skip)
        elif fields and sort:
            r = self.collection.find(query_dict, fields).sort(sort, 1)
        elif fields:
            r = self.collection.find(query_dict, fields)
        elif query_dict:
            r = self.collection.find(query_dict)
        else:
            r = self.collection.find(fields=fields)
        return [document for document in await r.to_list(length=5000)]

    # 用于前端展示列表+后端分页的场景
    async def page_query(self, query_dict=None, fields=None, page_size=2, page=1):
        skip = int(page_size) * (int(page) - 1)
        r = self.collection.find(query_dict, fields).limit(page_size).skip(skip)
        # counts = await self.collection.estimated_document_count()
        counts = await self.collection.count_documents(filter=query_dict)
        return [document for document in await r.to_list(length=5000)], counts

    async def find_data_by_id(self, id: str):
        result = self.collection.find_one({"_id": ObjectId(id)})
        return result

    async def find_data_by_index(self, index_name: str, index_value: any):
        result = self.collection.find_one({index_name: index_value})
        return result

    async def create_index(self, index_name: str, unique: bool = False):
        if unique:
            self.collection.create_index([(index_name, 1)], unique=True)
        else:
            self.collection.create_index([(index_name, 1)])

    async def drop_index(self, index_name: str):
        self.collection.drop_index(index_name)


async def test():
    task_db = AsyncMongoOps('task')
    r = await task_db.find(query_dict={'task_id': 'd5fdd16b-a51f-48aa-9a2e-03b369c4722c'}, fields={'_id': 0})
    print(r)
    return


if __name__ == "__main__":
    import asyncio

    asyncio.run(test())