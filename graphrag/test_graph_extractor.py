
from functools import reduce
import networkx as nx
from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from graphrag.entity_resolution import EntityResolution
from graphrag.graph_extractor import GraphExtractor
from graphrag.index import graph_merge
from rag.app import naive
from rag.utils import num_tokens_from_string
from neo4j import GraphDatabase
from loguru import logger as log

def graph2neo4j(graph:nx.Graph):
    """
    将当前的 python 里的 nx.Graph 里的数据同步到 neo4j ;
    确保节点的属性和关系的属性全部同步过去,节点的属性和关系的属性schema是未知的;
    如果和 neo4j 中现有的 node 和 relation 有冲突，则要融合进现有的节点。
    """
    # 连接到 Neo4j 数据库
    uri = "bolt://localhost:7687"  # Neo4j 的 URI
    username = "neo4j"               # 用户名
    password = "bitzero123"       # 密码

    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        # 创建或融合节点
        for node, attrs in graph.nodes(data=True):
            node_properties = {**attrs, 'id': node}
            session.run(f"""
                MERGE (n:Node {{id: $id}})
                ON CREATE SET n += {{{', '.join(f'{k}: ${k}' for k in attrs.keys())}}}
                ON MATCH SET n += {{{', '.join(f'{k}: ${k}' for k in attrs.keys())}}}
            """, **node_properties)

        # 创建或融合边
        for source, target, attrs in graph.edges(data=True):
            edge_properties = {**attrs, 'source': source, 'target': target}
            session.run(f"""
                MATCH (a:Node {{id: $source}}), (b:Node {{id: $target}})
                MERGE (a)-[r:CONNECTED_TO]->(b)
                ON CREATE SET r += {{{', '.join(f'{k}: ${k}' for k in attrs.keys())}}}
                ON MATCH SET r += {{{', '.join(f'{k}: ${k}' for k in attrs.keys())}}}
            """, **edge_properties)

    # 关闭连接
    driver.close()



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



if __name__ == "__main__":
    import json
    with open('/home/admin/python_projects/ragflow/graphrag/xiaodongwubook.json', 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        graph = nx.node_link_graph(json_data)
        graph2neo4j(graph)
    
    
    # test_extractor_file()