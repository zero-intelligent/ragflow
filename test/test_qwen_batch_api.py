
import pytest

from graphrag.index import batch_qwen_api_call

def test_qwen_batch_api(chunks = [],
                        left_token_count = 10000,
                        prompt_vars:dict = {},
                        filename = '/home/admin/python_projects/ragflow/inputs/1730103237434198216.txt'):
    
   
    chatresults = batch_qwen_api_call(chunks,left_token_count,prompt_vars)
    assert chatresults is not None
    assert len(chatresults) > 0

