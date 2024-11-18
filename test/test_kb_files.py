

import glob
import pytest
from api.db.services.document_service import DocumentService
from graphrag.utils import escape
from graphrag.db import driver
from loguru import logger as log

tenant_id:str = "7d19a176807611efb0f80242ac120006",
kb_id:str = "fb7c4312973b11ef88ed0242ac120006",
files:str = "pet_books/**/*.txt"
                      

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
    import pytest
    from api.apps import app

    docs = DocumentService.list_documents_in_dataset(kb_id,0,10000,order_by='create_time',descend=True,keywords='')
    with app.test_client() as client:
        txt_files = glob.glob(files, recursive=True)
        for file in txt_files:
            if not any([d['name'] in file for d in docs[0]]):
                # 上传文件和启动文件解析， // TODO 需要继续完善
                client.get('/v1/file/upload')
                client.get('/v1/document/start')
                pass
            
            
            