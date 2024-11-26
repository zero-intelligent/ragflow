import json
import re
from elasticsearch_dsl import Q
import networkx as nx
from collections import defaultdict
from api.db import LLMType
from api.db.services.document_service import DocumentService
from api.db.services.llm_service import LLMBundle
from api.db.services.document_service import DocumentService
from rag.nlp import rag_tokenizer, search
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
        if graph.has_node(node_id):
            raise ValueError(f"node_id:{node_id} exists, add failed!")
        graph.add_node(node_id,**node['properties']) 
        return {
            "added":node_id,
        }
        
    process_graph(tenant,kb,nodes,add_node)
    
  
def update_nodes(tenant, kb, nodes):
    if not all ([tenant,kb,nodes]):
        return
    def update_node(graph:nx.Graph,node):
        node_id = node['properties']['id']
        graph.nodes[node_id].update(**node['properties'])
        return {
                "added":node_id,
                "deleted":node_id,
            }
        
    process_graph(tenant,kb,nodes,update_node)
        
def delete_nodes(tenant, kb, nodes):
    """
    删除节点
    """
    if not all ([tenant,kb,nodes]):
        return
    def delete_node(graph:nx.Graph,node):
        node_id = node['properties']['id']
        if graph.has_node(node_id):
            graph.remove_node(node_id)
        return {"deleted":node_id}
        
    process_graph(tenant,kb,nodes,delete_node)


def delete_links(tenant, kb, links):
    if not all ([tenant,kb,links]):
        return
    # assure source_id not empty
    def remove_edge(graph:nx.Graph,link):
        start = link["start_node_id"]
        end = link["end_node_id"]
        if graph.has_edge(start,end):
            graph.remove_edge(start,end)
            return True
        return False
        
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
        start = link['start_node_id']
        end = link['end_node_id']
        graph.add_edge(start,end,**link['properties'])  # 添加边信息
        return True
        
    process_graph(tenant,kb,links,add_edge)
  
  
def update_links(tenant, kb, links):
    """
    更新边
    """
    if not all ([tenant,kb,links]):
        return
    
    def update_edge(graph:nx.Graph,link):
        start = link['start_node_id']
        end = link['end_node_id']
        if graph.has_edge(start,end):
            graph[start][end].update(**link['properties'])  # 更新边信息
            return False
        return True
        
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
            }
        }
        resp = ELASTICSEARCH.search(query,search.index_name(tenant.id))
        if not (hits := resp.body['hits']['hits']):
            raise Exception(f"search:{query} fail!no hits")
        if len(hits) > 1:
            hits.sort(key=lambda i:i['_source']['create_timestamp_flt'],reverse=True)
            log.warning(f"search:{query} fail! {len(hits)}>1 hits")
        
        graph_json_str = hits[0]['_source']['content_with_weight']
        graph_json = json.loads(graph_json_str)
        graph: nx.Graph = nx.node_link_graph(graph_json)
        
        added = []
        deleted = []
        for link in doc_links:
            r = process_fun(graph,link)
            if isinstance(r,dict):
                if r.get('added'):
                    added.append(r['added'])
                if r.get('deleted'):
                    deleted.append(r['deleted'])
                
                
        update_graph(tenant,kb,doc,graph,added,deleted)
        
    
def graph_nodes2chunks(graph:nx.Graph, llm_bdl:LLMBundle,added_node_ids):
    chunks = []
    for n in added_node_ids:
        attr = graph.nodes[n]
        chunk = {
            "name_kwd": n,
            "important_kwd": [n],
            "docnm_kwd": attr['source_id'],
            "title_tks": rag_tokenizer.tokenize(n),
            "content_with_weight": json.dumps({"name": n, **attr}, ensure_ascii=False),
            "content_ltks": rag_tokenizer.tokenize(attr["description"]),
            "knowledge_graph_kwd": "entity",
            "rank_int": attr["rank"],
            "weight_int": attr["weight"]
        }
        chunk["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(chunk["content_ltks"])
        chunks.append(chunk)

    chunks.append(
        {
            "content_with_weight": json.dumps(nx.node_link_data(graph), ensure_ascii=False, indent=2),
            "knowledge_graph_kwd": "graph"
        })
    return chunks

def update_graph(tenant,kb,doc,graph:nx.Graph,added_ids:list[str],deleted_ids:list[str]):
    """
        当内存图更新时，需要继续更新：
        1. 图对应的 chunks (包含图的节点chunk,图本身chunk,图的小区chunks,图的mindmap chunk)
        2. 图对应的 Embedding
        3. 图对应的 ES document
        
    """
    
    llm_bdl = LLMBundle(tenant.id, LLMType.CHAT, tenant.llm_id)
    
    def callback(*args,**kwargs):  # 空的callback, 以后按需修改
        pass
    
    graph_chunks = graph_nodes2chunks(graph,llm_bdl,added_ids)
        
    cks = task_executor.chuks2docs(kb.id,doc.id,graph_chunks)
    
    embd_mdl = LLMBundle(tenant.id, LLMType.EMBEDDING, tenant.embd_id, kb.language)
    
    log.info(f"embedding {len(cks)} chunks ...")
    tk_count = task_executor.embedding(cks, embd_mdl,callback=callback)

    # TODO : 此处需要探讨下是否删除旧的 entity_chunks 和 graph_chunks? 是否忽略 mindmap (因为mindmap 知识总结了书籍的目录结构),是否忽略小区抽取？
    query = Q("term", kb_id=kb.id) & Q("term", doc_id=doc.id) & Q("term", knowledge_graph_kwd="graph") | \
            Q("term", kb_id=kb.id) & Q("term", doc_id=doc.id) & Q("term", knowledge_graph_kwd="entity") & Q("terms", name_kwd=deleted_ids)
    log.info(f"es deleteByQuery {query} ...")
    ELASTICSEARCH.deleteByQuery(query, idxnm=search.index_name(tenant.id))
    
    log.info(f"es bulking {len(cks)} chunks ...")
    es_r = ELASTICSEARCH.bulk(cks, search.index_name(tenant))  
    if es_r:
        raise Exception(f"es bulk fail: {es_r}")
    
def get_doc(kb_id:str,source_id:str):
    match=re.match(r'^(.*?)(?=-graph|-\d)', source_id)
    if not match:
        raise ValueError(f"source_id {source_id} 需要'-graph'结尾或者'-数字'结尾!")
    
    doc_name = match.group(0)
    docs = DocumentService.model.select() \
        .where(DocumentService.model.name == doc_name, \
               DocumentService.model.kb_id==kb_id)
    if not docs:
        raise ValueError(f"document:{doc_name} do not exists in kb:{kb_id}!")
    if len(docs) > 1:
        raise ValueError(f"get {len(docs)} document by {doc_name} in kb:{kb_id}!")
    return docs[0]
    
    