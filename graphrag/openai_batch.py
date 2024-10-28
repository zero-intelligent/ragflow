import json
import os.path
import queue
from pathlib import Path
import time
from typing import List
from loguru import logger as log
from openai import OpenAI
from graphrag import prompt_messages
from rag.utils import num_tokens_from_string

file_path = './res/text'

client = OpenAI(
    api_key='sk-94156f9a5e684cba87df8727b56920e2',  # 如果您没有配置环境变量，请在此处用您的API Key进行替换
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 填写DashScope服务的base_url
)


def file_upload(file=file_path) -> str:
    # test.txt 是一个示例文件
    file_object = client.files.create(file=Path(file), purpose="batch")
    log.debug(f"file created:{file_object.model_dump_json()}")
    return file_object.id


def batch_create(file_id) -> str:
    batch = client.batches.create(
        input_file_id=file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    log.debug(f"batch created:{batch}")
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


def build_batch_input_block(custom_id, content, prompt_vars) -> json: 
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "qwen-plus",
            "messages": prompt_messages.process(content, prompt_vars)
        }
    }
    

def build_sub_texts_2d(chunks: List[str], left_token_count):
    BATCH_SIZE = 4
    texts, sub_texts, graphs = [], [], []
    cnt = 0

    for i in range(len(chunks)):
        tkn_cnt = num_tokens_from_string(chunks[i])
        if cnt + tkn_cnt >= left_token_count and texts:
            for b in range(0, len(texts), BATCH_SIZE):
                sub_texts.append(texts[b:b + BATCH_SIZE])

            texts = []
            cnt = 0
        texts.append(chunks[i])
        cnt += tkn_cnt
    if texts:
        for b in range(0, len(texts), BATCH_SIZE):
            sub_texts.append(texts[b:b + BATCH_SIZE])

    return sub_texts


def chunks2chat_input_lines(chunks: List[str],prompt_vars:dict,left_token_count:int):
    sub_texts_2d = build_sub_texts_2d(chunks, left_token_count)

    log.debug(f"########## sub_texts_2d={sub_texts_2d}")

    chat_input_lines = []
    
    for i, sub_text in enumerate(sub_texts_2d):
        line = [build_batch_input_block(f"{i}-{j}", line, prompt_vars)
                for j, line in enumerate(sub_text)]
        chat_input_lines.append(line)

    log.debug(f"########## lines={chat_input_lines}")
    
    return chat_input_lines
    
def batch_qwen_api_call(chunks: List[str]):
    '''
    调用 qwen  batch api 返回结果
    '''
    chat_input_lines = chunks2chat_input_lines(chunks)
    file = write_file(chat_input_lines)
    
    fid = file_upload(file)
    log.info(f"########## fid={fid}")

    bid = batch_create(fid)
    log.info(f"########## bid={bid}")

    chat_results = []
    while True:
        time.sleep(60)
        batch = query(bid)
        log.info(f"#### batch query ###### bid={bid},status:{batch.status}")
        if batch.status == 'completed':
            chat_results = get_results(batch.id)
            break
        elif batch.status in ['failed','expired','cancelling','cancelled']:
            raise ValueError(batch)

    chat_results = {c['id']:c['content'] for c in chat_results}
    
    # 校验是否有丢失的数据没有返回来
    input_ids = [line['custom_id'] for line in chat_input_lines]
    not_back_ids = set(input_ids) - set(chat_results.keys())
    if not_back_ids:
        log.error(f"以下id未返回：{not_back_ids}")
    return chat_results
        

def write_file(input_items, inputs_dir):
    try:
        f_name = str(time.time_ns()) + ".jsonl"
        file = Path(inputs_dir) / f_name
        log.info(f"########## file={file}")
        with open(file, 'w') as f:
            for data in input_items:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        return file
    except Exception as e:
        log.error(f"写入文件时发生错误: {e}")
        exit(1)
        

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
