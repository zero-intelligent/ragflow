import json
import os
from pathlib import Path
import time
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
        if batch.status in ['failed','expired','cancelling','cancelled']:
            raise ValueError(batch)
        return batch

    @tries()
    def file_upload(self,file:str='./res/text') -> str:
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
        assert all(isinstance(v,list) for v in id_messages.values()), "message must be list and element format :{'role':'system/user','content':'text'} "
        
        chat_input_lines = [{
                    "custom_id": id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.model,
                        "messages": assure_security(msg)
                    }
                } for id, msg in id_messages.items()]
        
        file = self.write_file(chat_input_lines)
        
        fid = self.file_upload(file)
        log.info(f"##########  uploaded {file},fid={fid}")

        bid = self.batch_create(fid)
        log.info(f"########## {file},bid={bid}")

        chat_results = []
        while True:
            time.sleep(int(os.environ.get('BATCH_QUERY_INTERVAL',60)))
            batch = self.get_batch(bid)
            log.info(f"#### batch query ###### bid={bid},status:{batch.status}")
            if batch.status == 'completed':
                chat_results = self.get_results(batch.output_file_id)
                break
        
        # 校验是否有丢失的数据没有返回来
        input_ids = [line['custom_id'] for line in chat_input_lines]
        not_back_ids = set(input_ids) - set(chat_results.keys())
        if not_back_ids:
            log.error(f"{file} 中的 custom_id in {not_back_ids} not back.")
        return chat_results
          

    def write_file(self,input_items, inputs_dir:str="./inputs"):
        try:
            f_name = str(time.time_ns()) + ".jsonl"
            file = Path(inputs_dir) / f_name
            Path(inputs_dir).mkdir(exist_ok=True)
            log.info(f"########## file={file}")
            with open(file, 'w') as f:
                for data in input_items:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
            return file
        except Exception as e:
            log.error("写入文件时发生错误" + str(e))
            exit(1)
            

