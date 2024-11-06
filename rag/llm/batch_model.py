from dataclasses import asdict, dataclass
import json
import os
import time
from typing import List, Optional, Tuple
from pathlib import Path
from loguru import logger as log
from openai import OpenAI
from rag.llm.chat_model import Base
from rag.utils import assure_security, md5_hash, tries
from rag.utils.redis_conn import REDIS_CONN
    
class BatchModel:
    model:str
    client:OpenAI
    
    def __init__(self,
                 model_instance: Base = None,
                 model: str = 'qwen-plus',
                 key:str = None,
                 base_url:str = None
        ):
        if isinstance(model_instance,Base):
            self.model = model_instance.model_name
            self.client = model_instance.client
        else:
            self.model = model
            self.client = OpenAI(key,base_url)
            
            
    @tries()
    def get_batch(self,bid):
        batch =  self.client.batches.retrieve(bid)
        log.info(f"#### batch query ###### bid={bid},status:{batch.status}")
        if batch.status in ['failed','expired','cancelling','cancelled']:
            raise ValueError(batch)
        return batch

    @tries()
    def file_upload(self,file:str) -> str:
        # test.txt 是一个示例文件
        file_object = self.client.files.create(file=Path(file), purpose="batch")
        log.debug(f"file created:{file_object.model_dump_json()}")
        return file_object.id

    @tries()
    def batch_create(self,file_id) -> str:
        batch = self.client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        log.debug(f"batch created:{batch}")
        return batch.id

    @tries()
    def get_results(self,output_file_id):
        content = self.client.files.content(output_file_id)
        # 拆分字节串
        json_strings = content.response.content.decode('utf-8').strip().split('\n')
        # 转换为 JSON 对象
        json_objects = [json.loads(json_str) for json_str in json_strings]

        return {item['custom_id']: item['response']['body']['choices'][0]['message']['content'] 
                for item in json_objects}
        
    def batch_api_call(self,id_messages: dict,chunk_size=1000):
        """
        对于大的 id_messages,拆分调用api
        """
        all_chat_results = {}
        items = sorted(list(id_messages.items()))  # 为了确保生成的 hash一致，此处需要排序
        for i in range(0, len(items), chunk_size):
            all_chat_results |= self.do_batch_api_call(items[i:i+chunk_size])
        return all_chat_results

    def do_batch_api_call(self,id_messages: List[Tuple]):
        '''
        调用 batch api 返回结果, 添加文件缓存，防止重复调用，浪费成本
        '''
        assert len(id_messages) > 0, "id_messages is invalid!"
        assert all(id and isinstance(messages,list) for id,messages in id_messages), "id not empty and message must be list and element format :{'role':'system/user','content':'text'} "
        
        chat_input_lines = [{
                    "custom_id": id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.model,
                        "messages": assure_security(msg)
                    }
                } for id, msg in id_messages]
        
        content = "\n".join([json.dumps(line, ensure_ascii=False) for line in chat_input_lines])
        id = md5_hash(content)
        task = get_task(id)
        
        if not task.local_input_file:
            file = Path(id).with_suffix(".jsonl")
            task.local_input_file = self.write_file(file,content)
        
        
        if not task.server_input_file_id:
            task.server_input_file_id = self.file_upload(task.local_input_file)
        
        if not task.batch_id:
            task.batch_id = self.batch_create(task.server_input_file_id)
        
        # 一般情况，任务在等待过程中中断，因此期望在此临时保存下任务。
        save_task(task)
        
        interval = int(os.environ.get('BATCH_QUERY_INTERVAL',60))
        log.info(f"waiting {interval}s to get_batch {task.batch_id} result.")
        while task.batch_status != 'completed':
            batch = self.get_batch(task.batch_id)
            task.batch_status = batch.status
            time.sleep(interval)
            
        if not task.server_output_file_id:
            batch = self.get_batch(task.batch_id)
            if not batch.output_file_id:
                if batch.error_file_id:
                     errors = self.get_results(batch.error_file_id)
                     raise Exception(f"get batch result error:{errors}")
            task.server_output_file_id = batch.output_file_id
            
        chat_results = self.get_results(task.server_output_file_id)
        save_task(task)
        
        if not task.local_output_file \
        or not Path(task.local_output_file).exists():
            filepath = Path(task.local_input_file).with_suffix('.out.json')
            with open(filepath, 'w') as file:
                json.dump(chat_results, file, ensure_ascii=False,indent=4)
            log.info(f"##########  chat_results dumps to {filepath}")
            task.local_output_file = str(filepath)
            save_task(task)
        else:
            with open(task.local_output_file, 'r') as file:
                chat_results = json.load(file)
            log.info(f"{task.local_output_file} exists, skip api_call")
            
        # 校验是否有丢失的数据没有返回来
        input_ids = [line['custom_id'] for line in chat_input_lines]
        not_back_ids = set(input_ids) - set(chat_results.keys())
        if not_back_ids:
            log.error(f"{task.local_input_file} 中的 custom_id in {not_back_ids} not back, may be secure blocked by server.")
    
        return chat_results

            
            
    def write_file(self,file, content, inputs_dir:str="./.cache/batch_llm"):
        """
         input_items 的 hash key 将作为缓存的 key ,确保不需要反复调用 LLM
        """
        try:
            
            file = Path(inputs_dir) / file
            Path(inputs_dir).mkdir(exist_ok=True)
            if file.exists():
                log.info(f"{file} exists, skip writing")
                return str(file)
            
            with open(file, 'w') as f:
                log.info(f"########## file={file}")
                f.write(content)
            return str(file)
        except Exception as e:
            log.error("写入文件时发生错误" + str(e))
            exit(1)
            

@dataclass
class BatchTaskInfo:
    """
    存储进度信息，避免中断后重复从头执行导致的成本增加
    """
    id: str
    local_input_file: Optional[str] = None
    server_input_file_id: Optional[str] = None
    batch_id: Optional[str] = None
    batch_status: Optional[str] = None
    server_output_file_id: Optional[str] = None
    local_output_file: Optional[str] = None
        

def get_task(id:str):
    if not REDIS_CONN.exist(id):
        return BatchTaskInfo(id=id)
    task_info = REDIS_CONN.get(id)
    task_dict = json.loads(task_info)
    return BatchTaskInfo(**task_dict)

def save_task(task):
    assert isinstance(task,BatchTaskInfo)
    REDIS_CONN.set_obj(task.id,asdict(task),exp=3600 * 24 * 7)
    
