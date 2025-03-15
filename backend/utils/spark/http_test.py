# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      http_test
   Description:
   Author:          Lijiamin
   date：           2025/2/10 17:21
-------------------------------------------------
   Change Activity:
                    2025/2/10 17:21
-------------------------------------------------
"""
from openai import OpenAI

api_key = "sk-SkscOkAaulJPG27PC176Ea8dFa3c4694B93a6c66A27686Ee"  # 请替换为您的 API Key
api_base = "http://maas-api.cn-huabei-1.xf-yun.com/v1"

client = OpenAI(api_key=api_key, base_url=api_base)

try:
    response = client.chat.completions.create(
        model="xdeepseekr1",
        messages=[{"role": "user", "content": "你好"}],
        stream=True,
        temperature=0.7,
        max_tokens=4096,
        extra_headers={"lora_id": "0"},
        stream_options={"include_usage": True}
    )

    full_response = ""
    for chunk in response:
        # 只对支持深度思考的模型才有此字段
        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[
            0].delta.reasoning_content is not None:
            reasoning_content = chunk.choices[0].delta.reasoning_content
            print(reasoning_content, end="", flush=True)  # 实时打印思考模型输出的思考过程每个片段

        if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)  # 实时打印每个片段
            full_response += content

    print("\n\n ------完整响应：", full_response)
except Exception as e:
    print(f"Error: {e}")