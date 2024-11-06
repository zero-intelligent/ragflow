# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License
"""
Reference:
 - [graphrag](https://github.com/microsoft/graphrag)
"""

import html
import inspect
import time
from pathlib import Path
import re
from collections.abc import Callable
from typing import Any
import networkx as nx
import pickle
from loguru import logger as log
from rag.utils import md5_hash

ErrorHandlerFn = Callable[[BaseException | None, str | None, dict | None], None]


def perform_variable_replacements(
    input: str, history: list[dict]=[], variables: dict | None ={}
) -> str:
    """Perform variable replacements on the input string and in a chat log."""
    result = input

    def replace_all(input: str) -> str:
        result = input
        if variables:
            for entry in variables:
                result = result.replace(f"{{{entry}}}", variables[entry])
        return result

    result = replace_all(result)
    for i in range(len(history)):
        entry = history[i]
        if entry.get("role") == "system":
            history[i]["content"] = replace_all(entry.get("content") or "")

    return result

english_and_digits__pattern = re.compile(r'[A-Za-z0-9]+')

def english_and_digits_of(text:str):
    # 使用正则表达式提取英文字符和数字
    matches = english_and_digits__pattern.findall(text)
    # 将匹配结果合并成一个字符串
    return ''.join(matches)

def clean_str(input: Any) -> str:
    """Clean an input string by removing HTML escapes, control characters, and other unwanted characters."""
    # If we get non-string input, just give it back
    if not isinstance(input, str):
        return input

    result = html.unescape(input.strip())
    # https://stackoverflow.com/questions/4324790/removing-control-characters-from-a-string-in-python
    return re.sub(r"[\"\x00-\x1f\x7f-\x9f]", "", result)


def full_to_half(s):
    """
    全角字符转半角
    """
    n = []
    for char in s:
        num = ord(char)
        if num == 0x3000:  # 全角空格直接转换
            num = 32
        elif 0xFF01 <= num <= 0xFF5E:  # 全角字符（除空格）根据关系转化
            num -= 0xfee0
        num = chr(num)
        n.append(num)
    return ''.join(n)


def dict_has_keys_with_types(
    data: dict, expected_fields: list[tuple[str, type]]
) -> bool:
    """Return True if the given dictionary has the given keys with the given types."""
    for field, field_type in expected_fields:
        if field not in data:
            return False

        value = data[field]
        if not isinstance(value, field_type):
            return False
    return True

def escape(input_string):
    if not isinstance(input_string,str):
        return input_string
    # 使用 str.replace 方法转义特殊字符
    escaped_string = input_string.replace('\\', '\\\\')  # 先转义反斜杠
    escaped_string = escaped_string.replace("'", "\\'")  # 转义单引号
    escaped_string = escaped_string.replace('"', '\\"')   # 转义双引号
    return escaped_string
            
def custom_str(obj):
    if isinstance(obj,nx.Graph):
        return f"nodes:{list(obj.nodes())},edges:{list(obj.edges())}"
    return str(obj)

# 给Graph定制化__str__函数，这样在使用 file_cache 时，就可以确保每个入参为 nx.Graph 的函数可以分辨出不同的Graph。
nx.Graph.__str__ = custom_str
         
def file_cache(func):
    """
     如果不指定文件名称，将会使用函数参数的 md5 hash 作为文件名
     函数的返回值必须是 list 或者 dict, 否则缓存装载会出错。
    """
    def decorator(*args, **kwargs):
        assert len(args) > 0
        if 'self' in inspect.signature(func).parameters:
            args_for_hash = args[1:]
        else:
            args_for_hash = args
        args_str = ",".join([str(arg) for arg in args_for_hash])
        cache_file = md5_hash(f"{func.__module__}.{func.__name__}({args_str},{str(kwargs)})")
        filepath = Path('.cache') / cache_file
        
        if filepath.exists() and filepath.stat().st_mtime + 7 * 24 * 3600 > time.time():
            log.info(f"{func.__module__}{func.__name__} using cache file {filepath}.")
            with open(filepath, 'rb') as f:
                return pickle.load(f)
        else:
            ret = func(*args, **kwargs)
            with open(filepath, 'wb') as f:
                pickle.dump(ret, f)
            return ret
    return decorator