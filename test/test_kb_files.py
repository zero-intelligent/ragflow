

import glob
import io
import mimetypes
from types import SimpleNamespace
import pytest
from api.db.services.document_service import DocumentService
from api.db.services.file_service import FileService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import UserService
from werkzeug.datastructures import FileStorage
from graphrag.utils import escape
from graphrag.db import driver
from loguru import logger as log

tenant_id:str = "7d19a176807611efb0f80242ac120006",
kb_id:str = "fb7c4312973b11ef88ed0242ac120006",
files:str = "pet_books/**/*.txt"
user_name:str = 'ragflow'
                      

def test_kb_files_competence():
    txt_files = glob.glob(files, recursive=True)
    docs = DocumentService.list_documents_in_dataset(kb_id,0,10000,order_by='create_time',descend=True,keywords='')
    lost_cnt = 0
    
    for file in txt_files:
        if not any([d['name'] in file for d in docs[0]]):
            log.warning(f"{file} not in docs.")
            lost_cnt += 1
    assert lost_cnt == 0, f"{lost_cnt} files lost."
    
    
def test_neo4j_entity_source_id_competence():
    docs = DocumentService.list_documents_in_dataset(kb_id,0,10000,order_by='create_time',descend=True,keywords='')
    lost_cnt = 0
    with driver.session() as session:
        for doc in docs[0]:
            filename = escape(doc['name'])
            source_exists_query = f"match (n) where n.source_id contains '{filename}' return n limit 1"
            result = session.run(source_exists_query)
            if not result.single():
                log.warning(f"{doc['name']} not found entity with source_id!")
                lost_cnt += 1
    
    assert lost_cnt == 0, f'{lost_cnt} file not imported to neo4j.'



def scan_all_files2kb():
    docs = DocumentService.list_documents_in_dataset(kb_id,0,10000,order_by='create_time',descend=True,keywords='')
    
    txt_files = glob.glob(files, recursive=True)
    lost_files = [file for file in txt_files if not any([d['name'] in file for d in docs[0]])]
    
    kb = KnowledgebaseService.get_by_id(kb_id)
    user = UserService.get_by_nickname(user_name)
    
    for filename in lost_files:
        with open(filename, 'rb') as f:
            file_content = f.read()
            
            # 创建一个内存中的文件流
            file_stream = io.BytesIO(file_content)
            
            # 创建 FileStorage 对象
            file_storage = FileStorage(
                stream=file_stream,
                filename=filename,
                name=filename,  # 表单字段名可以使用文件名
                content_type=mimetypes.guess_type(filename)[0] or 'application/octet-stream',  # 获取文件的 MIME 类型
                content_length=len(file_content)
            )
            err, _ = FileService.upload_document(kb, [file_storage], user.id)
            if err:
                log.warning(f"{filename} upload fail,{err}")
            
            
        

            
        
            
            