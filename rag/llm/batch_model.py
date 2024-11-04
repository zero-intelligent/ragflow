from dataclasses import asdict, dataclass
import hashlib
import json
import os
import time
import atexit
from typing import Optional
from pathlib import Path
from loguru import logger as log
from openai import OpenAI
from rag.llm.chat_model import Base
from rag.utils import assure_security, tries
    
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
        
    
    def batch_api_call(self,id_messages: dict):
        '''
        调用 batch api 返回结果, 添加文件缓存，防止重复调用，浪费成本
        '''
        assert isinstance(id_messages,dict) and len(id_messages) > 0, "id_messages is invalid!"
        assert all(id and isinstance(messages,list) for id,messages in id_messages.items()), "id not empty and message must be list and element format :{'role':'system/user','content':'text'} "
        
        chat_input_lines = [{
                    "custom_id": id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.model,
                        "messages": assure_security(msg)
                    }
                } for id, msg in id_messages.items()]
        
        content = "\n".join([json.dumps(line, ensure_ascii=False) for line in chat_input_lines])
        id = self.hash(content)
        task = get_task(id)
        
        if not task.local_input_file:
            task.local_input_file = str(self.write_file(file=id,content=content))
        
        
        if not task.server_input_file_id:
            task.server_input_file_id = self.file_upload(task.local_input_file)
        
        if not task.batch_id:
            task.batch_id = self.batch_create(task.server_input_file_id)
        
        # 一般情况，任务在等待过程中中断，因此期望在此临时保存下任务。
        save_tasks()

        while task.batch_status != 'completed':
            time.sleep(int(os.environ.get('BATCH_QUERY_INTERVAL',60)))
            batch = self.get_batch(task.batch_id)
            task.batch_status = batch.status
            
        if not task.server_output_file_id:
            task.server_output_file_id = batch.output_file_id
            
        chat_results = self.get_results(task.server_output_file_id)
        save_tasks()
        
        if not task.local_output_file \
        or not Path(task.local_output_file).exists():
            filepath = Path(task.local_input_file).with_suffix('.out.json')
            with open(filepath, 'w') as file:
                json.dump(chat_results, file, ensure_ascii=False,indent=4)
            log.info(f"##########  chat_results dumps to {filepath}")
            task.local_output_file = str(file)
            save_tasks()
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
          

    def hash(self,content:str):
        hash_object = hashlib.md5()
        # 更新哈希对象
        hash_object.update(content.encode('utf-8'))
        # 获取哈希值
        hash_value = hash_object.hexdigest()
        return hash_value
            
            
    def write_file(self,file, content, inputs_dir:str="./inputs"):
        """
         input_items 的 hash key 将作为缓存的 key ,确保不需要反复调用 LLM
        """
        try:
            
            file = Path(inputs_dir) / file
            Path(inputs_dir).mkdir(exist_ok=True)
            if file.exists():
                log.info(f"{file} exists, skip writing")
                return file
            
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
    if id not in batch_tasks:
        batch_tasks[id] = BatchTaskInfo(id=id)
    return batch_tasks[id]

def load_tasks():
    batch_tasks = {}
    if Path(tasks_file).exists():
        with open(tasks_file, 'r') as file:
            dict_tasks = json.load(file)
        for task in dict_tasks:
            batch_tasks[task['id']] = BatchTaskInfo(**task)
        log.info(f"{len(batch_tasks)} tasks load from {tasks_file}")
    return batch_tasks

def save_tasks():
    dict_tasks = [asdict(task) for task in batch_tasks.values()]
    with open(tasks_file, 'w', encoding='utf-8') as file:
        file.write(json.dumps(dict_tasks, indent=4))
    log.info(f"{len(batch_tasks)} tasks saved to {tasks_file}")
    
# 存储进度信息
tasks_file:str = ".tasks.json"

# 启动时，装载上次失败的任务
batch_tasks = load_tasks()

# 退出时，确保所有任务进度保存
atexit.register(save_tasks)
