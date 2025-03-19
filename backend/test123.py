# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      test123
   Description:
   Author:          Lijiamin
   date：           2025/2/26 22:15
-------------------------------------------------
   Change Activity:
                    2025/2/26 22:15
-------------------------------------------------
"""
import hashlib
import requests
from urllib.parse import urlparse

URL = "https://model.iflytek.com/api/v0.1/ci"
KEY = "88795379d56f46be9679ecc548d868d4"
SECRET = "DsX2$i#3RVn^l@5z*9v1dGUCrqFbEONk"


def build_api_key(path, params):
    values = "".join([str(params[k]) for k in sorted((params or {}).keys())
                      if k not in ("_key", "_secret") and not isinstance(params[k], (dict, list))])
    _secret = "".join([path, SECRET, values]).encode("utf-8")
    params["_secret"] = hashlib.sha1(_secret).hexdigest()
    params["_key"] = KEY
    return params


# "_type:project",
def get_ci(data):
    payload = build_api_key(urlparse(URL + "/s").path, data)
    return requests.get(URL + "/s", params=payload).json()


def add_ci(data):
    data["exist_policy"] = "replace"
    payload = build_api_key(urlparse(URL).path, data)
    res = requests.post(URL, json=payload)
    print(res.status_code)
    return res.json()


def update_ci(payload, ci_id=None):
    url = "{url}/{ci_id}".format(url=URL, ci_id=ci_id) if ci_id is not None else URL
    payload = build_api_key(urlparse(url).path, payload)
    return requests.put(url, json=payload).json()


if __name__ == "__main__":
    data = {
        "sn": "asdfas1",
        "status": "online",
        "manufacturer": 8661,
        "assetCode": "asdfasdf12312",
        "ci_type": "Switch_1"
    }
    # data = {
    #     "sn": "abc123",
    #     "ci_type": "loadblance"
    # }
    res = add_ci(data)
    print(res)
