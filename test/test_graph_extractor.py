
from functools import reduce
import pytest
import logging
import networkx as nx
from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from graphrag.entity_resolution import EntityResolution
from graphrag.graph_extractor import GraphExtractor
from graphrag.index import graph_merge
from rag.app import naive
from rag.utils import num_tokens_from_string

log = logging.getLogger(__name__)

@pytest.fixture
def graphExtractor():
    return GraphExtractor()


def test_extractor_file(tenant_id = "7d19a176807611efb0f80242ac120006",
                        llm_id = "qwen-plus",
                        filename = '/home/admin/python_projects/MedicalGPT/data/pretrain/pet_books/094小动物疾病学.pdf.txt'):
    
    parser_config = {"chunk_token_num": 512, "delimiter": "\n!?。；！？", "layout_recognize": False}
    with open(filename, 'rb') as file:
        binary = file.read()
    
    def progress(prog=1.0,msg=""):
        log.info(f"progess:{prog},{msg}")
    chunks = naive.chunk(filename, binary, from_page=0, to_page=10000, section_only=True,parser_config=parser_config,callback=progress)
    
    entity_types = "宠物种类,品种,年龄,性别,体重,体温,疾病,症状,药物,治疗方法,诊断测试,体征,器官或系统,疫苗,动物行为,过敏源,预后,环境因素,营养,食物,饮水情况,生活习惯,过敏反应,居住环境,寄生虫".split(',')
    llm_bdl = LLMBundle(tenant_id, LLMType.CHAT, llm_id)
    extract = GraphExtractor(llm_bdl)
    left_token_count = llm_bdl.max_length - extract.prompt_token_count - 1024
    left_token_count = min(llm_bdl.max_length * 0.4, left_token_count)
    
    texts, graphs = [], []
    cnt = 0
    for i in range(len(chunks)):
        texts.append(chunks[i])
        tkn_cnt = num_tokens_from_string(chunks[i])
        cnt += tkn_cnt
        if texts and (cnt+tkn_cnt >= left_token_count or i == len(chunks)-1):
            graph = extract(["\n".join(texts)], {"entity_types": entity_types}, callback=progress)
            graphs.append(graph)
            texts = []
            cnt = 0
        

    graph = reduce(graph_merge, graphs) if graphs else nx.Graph()
    er = EntityResolution(llm_bdl)
    graph = er(graph).output
    assert graph is not None

