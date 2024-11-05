# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License
"""
Reference:
 - [graphrag](https://github.com/microsoft/graphrag)
"""

import html
import re
from collections.abc import Callable
from typing import Any

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
