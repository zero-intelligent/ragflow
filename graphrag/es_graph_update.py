import json
import re
from elasticsearch_dsl import Q
import networkx as nx
from collections import defaultdict
from api.db import LLMType
from api.db.services.document_service import DocumentService
from api.db.services.llm_service import LLMBundle
from api.db.services.document_service import DocumentService
from graphrag.index import graph2chunks
from rag.nlp import search
from rag.svr import task_executor
from rag.utils.es_conn import ELASTICSEARCH
from loguru import logger as log

# 当新增加的节点找不到附着文档时，则从这个文档开始附着
default_attach_doc = '01宠物疾病/【04】《兽医组织学彩色图谱（第2版）》.pdf.txt-graph'
    
def create_nodes(tenant, kb, nodes):
    if not all ([tenant,kb,nodes]):
        return
    for node in nodes:
        if not node.get('properties'):
            node['properties'] = {}
        if not node['properties'].get('source_id'):
            node['properties']['source_id'] = default_attach_doc

    def add_node(graph:nx.Graph,node):
        node_id = node['properties']['id']
        graph.add_node(node_id,**node) 
        
    process_graph(tenant,kb,nodes,add_node)
    
  
def update_nodes(tenant, kb, nodes):
    if not all ([tenant,kb,nodes]):
        return
    def update_node(graph:nx.Graph,node):
        node_id = node['properties']['id']
        graph.nodes[node_id].update(node)
        
    process_graph(tenant,kb,nodes,update_node)
        
def delete_nodes(tenant, kb, node_names):
    """
    删除节点
    """
    if not all ([tenant,kb,node_names]):
        return
    def delete_node(graph:nx.Graph,node):
        node_id = node['properties']['id']
        if graph.has_node(node_id):
            graph.remove_node(node_id)
        
    process_graph(tenant,kb,node_names,delete_node)


def delete_links(tenant, kb, links):
    if not all ([tenant,kb,links]):
        return
    # assure source_id not empty
    def remove_edge(graph:nx.Graph,link):
        start = link["start_id"]
        end = link["end_id"]
        if graph.has_edge(start,end):
            graph.remove_edge(start,end)
        
    process_graph(tenant,kb,links,remove_edge)
    

def add_links(tenant, kb, links):
    if not all ([tenant,kb,links]):
        return
    for link in links:
        if not link.get('properties'):
            link['properties'] = {}
        if not link['properties'].get('source_id'):
            link['properties']['source_id'] = default_attach_doc
            
    def add_edge(graph:nx.Graph,link):
        start = link["start"]['properties']['id']
        end = link["end"]['properties']['id']
        graph.add_edge(start,end,**link['properties'])  # 添加边信息
        
    process_graph(tenant,kb,links,add_edge)
  
  
def update_links(tenant, kb, links):
    """
    更新边
    """
    if not all ([tenant,kb,links]):
        return
    
    def update_edge(graph:nx.Graph,link):
        start = link["start"]['properties']['id']
        end = link["end"]['properties']['id']
        graph[start][end].update(link)  # 更新边信息
        
    process_graph(tenant,kb,links,update_edge)  

def process_graph(tenant, kb, nodes_or_links,process_fun):
    """
    先按照 doc_id 分组
    每个 doc_id 内部统处理：增删改查节点和边
    """
    grouped_data = defaultdict(list)
    for link in nodes_or_links:
        doc = get_doc(kb.id, link['properties'].get("source_id"))
        grouped_data[doc].append(link)
    
    for doc, doc_links in grouped_data.items():
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"knowledge_graph_kwd": "graph"}},
                        {"term": {"kb_id": kb.id}},
                        {"term": {"doc_id": doc.id}},
                    ]
                }
            },
            "_source": ["content_with_weight"],
            "size": 1
        }
        resp = ELASTICSEARCH.search(query,search.index_name(tenant.id))
        if not (hits := resp.body['hits']['hits']):
            log.error(f"search:{query} fail!")
            return
        graph_json_str = hits[0]['_source']['content_with_weight']
        graph_json = json.loads(graph_json_str)
        graph: nx.Graph = nx.node_link_graph(graph_json)
        
        for link in doc_links:
            process_fun(graph,link)
    
        update_graph(tenant,kb,doc,graph)
        
def update_graph(tenant,kb,doc,graph:nx.Graph):
    """
        当内存图更新时，需要继续更新：
        1. 图对应的 chunks (包含图的节点chunk,图本身chunk,图的小区chunks,图的mindmap chunk)
        2. 图对应的 Embedding
        3. 图对应的 ES document
        
    """
    
    llm_bdl = LLMBundle(tenant.id, LLMType.CHAT, tenant.llm_id)
    
    def callback(*args,**kwargs):  # 空的callback, 以后按需修改
        pass
    
    graph_chunks = graph2chunks(graph,llm_bdl,callback)
        
    cks = task_executor.chuks2docs(kb.id,doc.id,graph_chunks)
    
    embd_mdl = LLMBundle(tenant.id, LLMType.EMBEDDING, tenant.embd_id, kb.language)
    
    tk_count = task_executor.embedding(cks, embd_mdl,callback=callback)

    # TODO : 此处需要探讨下是否删除旧的 entity_chunks 和 graph_chunks? 是否忽略 mindmap (因为mindmap 知识总结了书籍的目录结构),是否忽略小区抽取？
    query = Q("term", kb_id=kb.id) & \
            Q("term", doc_id=doc.id) & \
            (Q("exists", field="name_kwd") | Q("term", knowledge_graph_kwd="graph"))
    
    ELASTICSEARCH.deleteByQuery(query, idxnm=search.index_name(tenant.id))
    
    es_r = ELASTICSEARCH.bulk(cks, search.index_name(tenant))  
    if not es_r:
        return
    
    chunk_count = len(set([c["_id"] for c in cks]))
    DocumentService.increment_chunk_num(doc.id, kb.id, tk_count, chunk_count, 0)
    
def get_doc(kb_id:str,source_id:str):
    match=re.match(r'^(.*?)(?=-graph|-\d)', source_id)
    if not match:
        raise ValueError(f"source_id {source_id} 需要'-graph'结尾或者'-数字'结尾!")
    
    doc_name = match.group(0)
    doc_id = DocumentService.model.select(DocumentService.model.id) \
        .where(DocumentService.model.name == doc_name, \
               DocumentService.model.kb_id==kb_id)
    if not doc_id:
        raise ValueError(f"document:{doc_name} do not exists in kb:{kb_id}!")
    return doc_id[0]
    
    