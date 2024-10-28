
from functools import reduce
import networkx as nx
from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from graphrag.entity_resolution import EntityResolution
from graphrag.graph_extractor import GraphExtractor
from graphrag.index import graph_merge
from rag.app import naive
from rag.utils import num_tokens_from_string
from loguru import logger as log

def test_extractor_file(tenant_id = "7d19a176807611efb0f80242ac120006",
                        llm_id = "moonshot-v1-128k",
                        filename = '/home/admin/python_projects/MedicalGPT/data/pretrain/pet_books/094小动物疾病学.pdf.txt'):
    
    parser_config = {"chunk_token_num": 512, "delimiter": "\n!。；?！？", "layout_recognize": False}
    with open(filename, 'rb') as file:
        binary = file.read()
    
    def progress(prog=1.0,msg=""):
        log.info(f"progess:{prog},{msg}")
    
    log.info(f"naive.chunking with config:{parser_config}")
    chunks = naive.chunk(filename, binary, from_page=0, to_page=10000, section_only=True,parser_config=parser_config,callback=progress)
    log.info(f"{filename} chunked")
    
    entity_types = "宠物种类,品种,年龄,性别,体重,体温,疾病,症状,药物,治疗方法,诊断测试,体征,器官或系统,疫苗,动物行为,过敏源,预后,环境因素,营养,食物,饮水情况,生活习惯,过敏反应,居住环境,寄生虫,保定法,检查方法,流行病学,病变".split(',')
    llm_bdl = LLMBundle(tenant_id, LLMType.CHAT, llm_id)
    extract = GraphExtractor(llm_bdl)
    left_token_count = llm_bdl.max_length - extract.prompt_token_count - 1024
    left_token_count = min(int(llm_bdl.max_length * 0.3), left_token_count)
    
    texts, graphs = [], []
    cnt = 0
    for i in range(len(chunks)):
        texts.append(chunks[i])
        cnt += num_tokens_from_string(chunks[i])
        log.info(f"chunk:{i}/{len(chunks)},token_cnt:{cnt}/{left_token_count},{1.0*i/len(chunks):.2%}")
        if texts and (cnt >= left_token_count or i == len(chunks)-1):
            log.info(f"extracting:{len(texts)} chunks, last one: {"\n".join(texts).replace('\n',' ')}")
            graph = extract(["\n".join(texts)], {"entity_types": entity_types}, callback=progress).output
            log.info(f"graph,nodes:{graph.number_of_nodes()},edges:{graph.number_of_edges()}")
            graphs.append(graph)
            texts = []
            cnt = 0
        
    log.info(f"reduce of graph cnt:{len(graphs)}")
    graph = reduce(graph_merge, graphs) if graphs else nx.Graph()
    log.info(f"EntityResolution of graph nodes cnt:{len(graph)}")
    er = EntityResolution(llm_bdl)
    graph = er(graph).output
    
    assert graph is not None
    assert graph.nodes.get('细小病毒',{}).get('entity_type') == '疾病'
    assert graph.has_edge('细小病毒','胃肠炎')


def validte_json_files():
    import json

    with open('/home/admin/python_projects/ragflow/inputs/1730103237434198216.txt', 'r') as f:
        for line in f:
            try:
                json.loads(line)
            except json.JSONDecodeError:
                print(f'Invalid JSON: {line.strip()}')
            
if __name__ == "__main__":
    
    validte_json_files()