#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import functools
import hashlib
import inspect
import os
import re
import time
from typing import List
import tiktoken
from loguru import logger as log

def singleton(cls, *args, **kw):
    instances = {}

    def _singleton():
        key = str(cls) + str(os.getpid())
        if key not in instances:
            instances[key] = cls(*args, **kw)
        return instances[key]

    return _singleton


def rmSpace(txt):
    txt = re.sub(r"([^a-z0-9.,\)>]) +([^ ])", r"\1\2", txt, flags=re.IGNORECASE)
    return re.sub(r"([^ ]) +([^a-z0-9.,\(<])", r"\1\2", txt, flags=re.IGNORECASE)


def findMaxDt(fnm):
    m = "1970-01-01 00:00:00"
    try:
        with open(fnm, "r") as f:
            while True:
                l = f.readline()
                if not l:
                    break
                l = l.strip("\n")
                if l == 'nan':
                    continue
                if l > m:
                    m = l
    except Exception as e:
        pass
    return m

  
def findMaxTm(fnm):
    m = 0
    try:
        with open(fnm, "r") as f:
            while True:
                l = f.readline()
                if not l:
                    break
                l = l.strip("\n")
                if l == 'nan':
                    continue
                if int(l) > m:
                    m = int(l)
    except Exception as e:
        pass
    return m


encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    try:
        num_tokens = len(encoder.encode(string))
        return num_tokens
    except Exception as e:
        pass
    return 0

def build_sub_texts_2d(chunks: List[str], left_token_count):
    BATCH_SIZE = 4
    texts, sub_texts = [], []
    cnt = 0
    for i in range(len(chunks)):
        tkn_cnt = num_tokens_from_string(chunks[i])
        if texts and cnt + tkn_cnt >= left_token_count:
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


def truncate(string: str, max_len: int) -> str:
    """Returns truncated text if the length of text exceed max_len."""
    return encoder.decode(encoder.encode(string)[:max_len])


def args_to_str(args,kwargs,max_len=128):
    s1 = [str(r)[:max_len] for r in args]
    s2 = [f"{k}={str(w)[:max_len]}" for k,w in kwargs]
    return f"[{s1},{s2}]"

unsecuring_words = ["台湾","taiwan","台灣"]

def assure_security(input:str):
    if not isinstance(input,str):
        return input
    output = input
    for w in unsecuring_words:
        output = output.replace(w,"")
    return output

def md5_hash(content:str):
    assert content, 'content not empty!'
    hash_object = hashlib.md5()
    # 更新哈希对象
    hash_object.update(content.encode('utf-8'))
    # 获取哈希值
    hash_value = hash_object.hexdigest()
    
    # log.debug(f"hash:{content} to:{hash_value}")
    return hash_value
    
    
def tries(max_try_cnt:int=3,interval:int=10):
    """
     重试次数装饰器
     被装饰的函数将最多尝试执行N(默认=3) 次，直到成功。
     如果连续N次都失败了,则返回最后一次异常信息。
     为确保稳定性，每次间隔期间，都会 sleep interval(默认为10)秒。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_try_cnt):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i < max_try_cnt:
                        calframe = inspect.getouterframes(inspect.currentframe(), 2)
                        log.error(f"Error {calframe[1][3]} {i+1}rd call function '{func.__name__}',args:'{args_to_str(args,kwargs)}': {e}")
                        time.sleep(interval)
                    else: # 最后一次还是抛异常，重新抛出异常
                        raise
        return wrapper
    return decorator

    

