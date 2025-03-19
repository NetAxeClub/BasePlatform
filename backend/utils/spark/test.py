import SparkApi

# 以下密钥信息从服务管控页面获取：https://training.xfyun.cn/modelService
appid = "401a49f6"  # 填写控制台中获取的 APPID 信息
api_secret = "NDI3YjMzZTU3MmRiNWRjYzA3MDJjZWVl"  # 填写控制台中获取的 APISecret 信息
api_key = "df310a5ccabbb203a7946fc6863952c0"  # 填写控制台中获取的 APIKey 信息

# 从服务管控获取要访问服务的serviceID：https://training.xfyun.cn/modelService
domain = "xdeepseekr1"

# 云端环境的服务地址 https://maas-api.cn-huabei-1.xf-yun.com/v1
Spark_url = "wss://maas-api.cn-huabei-1.xf-yun.com/v1.1/chat"  # 微调模型地址，从服务管控页面查看：https://training.xfyun.cn/modelService

text = []


# length = 0

def getText(role, content):
    jsoncon = {}
    jsoncon["role"] = role
    jsoncon["content"] = content
    text.append(jsoncon)
    return text


def getlength(text):
    length = 0
    for content in text:
        temp = content["content"]
        leng = len(temp)
        length += leng
    return length


def checklen(text):
    while (getlength(text) > 8000):
        del text[0]
    return text


if __name__ == '__main__':
    text.clear
    while (1):
        Input = input("\n" + "我:")
        question = checklen(getText("user", Input))
        SparkApi.answer = ""
        print("星火:", end="")
        SparkApi.main(appid, api_key, api_secret, Spark_url, domain, question)
        res = getText("assistant", SparkApi.answer)
        print(''.join([x['content'] for x in res if x['role'] == 'assistant']))
