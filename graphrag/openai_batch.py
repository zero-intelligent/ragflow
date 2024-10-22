import json
import os.path
import queue
from pathlib import Path

from openai import OpenAI

file_path = './res/text'

client = OpenAI(
    api_key='sk-94156f9a5e684cba87df8727b56920e2',  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 填写DashScope服务的base_url
)


def file_upload(file=file_path) -> str:
    # test.txt 是一个示例文件
    file_object = client.files.create(file=Path(file), purpose="batch")
    print(file_object.model_dump_json())
    return file_object.id


def batch_create(file_id) -> str:
    batch = client.batches.create(
        input_file_id=file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    print(batch)
    return batch.id


def query(batch_id):
    batch = client.batches.retrieve(batch_id)
    return batch


def get_results(bid):
    content = client.files.content(query(bid).output_file_id)
    # 拆分字节串
    json_strings = content.response.content.decode('utf-8').strip().split('\n')
    # 转换为 JSON 对象
    json_objects = [json.loads(json_str) for json_str in json_strings]

    res = [{
        'id': item['custom_id'],
        'content': item['response']['body']['choices'][0]['message']['content'],
        'completion_tokens': item['response']['body']['usage']['completion_tokens'],
        'prompt_tokens': item['response']['body']['usage']['prompt_tokens'],
        'total_tokens': item['response']['body']['usage']['total_tokens'],

    } for item in json_objects]

    return res


def write_file(content, f_name, inputs_dir='./'):
    try:
        with open(os.path.join(inputs_dir, f_name), 'w') as file:
            file.write(content)
    except IOError as e:
        print(f"写入文件时发生错误: {e}")


task_buf = queue.Queue(maxsize=5)

if __name__ == '__main__':
    # write2File("hello", 'bbb', 'C:\\dev\\zero\code\\ragflow\\graphrag\\res')
    # resp = get_results('batch_27121751-7104-4ef3-8b0f-7b431f7f5fd4')
    # print(resp)
    # batches = client.batches.list()
    # print(batches)

    # fid = file_upload()
    # bid = batch(fid)
    # print(f'####{fid}######## {bid}')
    batch = query('batch_27121751-7104-4ef3-8b0f-7b431f7f5fd4')
    raise ValueError('llm chat batch error!', batch)
    fid = batch.output_file_id
    print(fid)
