import hashlib
import json
import uuid
from datetime import datetime

import networkx as nx
from elasticsearch_dsl import Q

from api.db import LLMType
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMBundle
from api.utils.api_utils import get_data_error_result
from graphrag.mind_map_extractor import MindMapExtractor
from rag.nlp import search, rag_tokenizer
from rag.svr import task_executor
from rag.utils.es_conn import ELASTICSEARCH
from loguru import logger as log

# 当新增加的节点找不到附着文档时，则从这个文档开始附着
default_attach_doc = '21小动物疾病临床症状Clinical_Signs_in_Small_Animal_Medicine.pdf.txt'


def upsert_nodes(tenant_id, kb_id, nodes):
    for node in nodes:
        update_node(tenant_id, kb_id, node['id'], node)
        

def create_node(tenant_id, kb_id, node_name, node_attrs):
    node_chunk = build_node_chunk(kb_id, node_name, node_attrs)
    graph_chunk = build_graph_chunk(None, node_name, node_attrs)
    chunks = node_chunk + graph_chunk
    
  
# node_attrs: name, description, doc_id rank  weight
def update_node(tenant_id, kb_id, node_name, node_attrs):
    if node_attrs.get("rank", 0) == 0:
        log.warning(f"Ignore entity: {node_name}")
        return


    node_chunk = build_node_chunk(kb_id, node_name, node_attrs)
    graph_chunk = build_graph_chunk(None, node_name, node_attrs)
    # TODO mindmap_chunk

    chunks = node_chunk + graph_chunk

    e, kb = KnowledgebaseService.get_by_id(kb_id)
    if not e:
        return get_data_error_result(retmsg=f"Can't find knowledgebase {kb_id}!")

    embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING, llm_name=kb.embd_id, lang=kb.language)
    tk_count = task_executor.embedding(chunks, embd_mdl, kb.parser_config)

    query = {
            "query": {
                "term": {
                    "name_kwd": node_name
                }
            }
        }
    old_entity = ELASTICSEARCH.get_by_query(query, search.index_name(tenant_id))
    # 实体-更新/新增
    if old_entity:
        # 更新，es中 _id不变
        del node_chunk['_id']
        query = {
            "query": {
                "term": {
                    "name_kwd": node_name
                }
            }
        }
        r = ELASTICSEARCH.updateByQuery(query, node_chunk)
        if not r:
            raise ValueError('更新实体失败！', r)

    else:
        # 新增
        es_r = ELASTICSEARCH.bulk([node_chunk], search.index_name(tenant_id))
        if es_r:
            ELASTICSEARCH.deleteByQuery(
                Q("match", name_kwd=node_chunk["name_kwd"]), idxnm=search.index_name(tenant_id))
        else:
            DocumentService.increment_chunk_num(
                node_chunk.get("doc_id"), kb_id, tk_count, 1, 0)

    # graph 更新：
    del graph_chunk['_id']
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"knowledge_graph_kwd": "graph"}},
                    {"term": {"doc_id": graph_chunk['doc_id']}}
                ]
            }
        }
    }

    r = ELASTICSEARCH.updateByQuery(query, graph_chunk)
    if not r:
        raise ValueError('更新实体失败！', r)


        
def delete_nodes(tenant_id, kb_id, node_names, doc_id):
    ELASTICSEARCH.deleteByQuery({
        "query": {
            "term": {
                "name_kwd": node_names
            }
        }
    }, idxnm=search.index_name(tenant_id))

    ELASTICSEARCH.deleteByQuery({
        "query": {
            "bool": {
                "must": [
                    {"term": {"knowledge_graph_kwd": "graph"}},
                    {"term": {"doc_id": doc_id}}
                ]
            }
        }
    }, idxnm=search.index_name(tenant_id))


def upsert_links(tenant_id, kb_id, links):
    for name,attrs in links.items():
        upsert_link(tenant_id, kb_id, name, attrs)
        
def upsert_link(tenant_id, kb_id, node_name, **node_attrs):
    pass

def delete_links(tenant_id, kb_id, links):
    pass


def build_mindmap_chunk(llm_bdl, chunks_by_naive):
    mindmap = MindMapExtractor(llm_bdl)
    mg = mindmap(chunks_by_naive).output
    if not len(mg.keys()): return {}

    print(json.dumps(mg, ensure_ascii=False, indent=2))

    return {
        "content_with_weight": json.dumps(mg, ensure_ascii=False, indent=2),
        "knowledge_graph_kwd": "mind_map"
    }


def build_node_chunk(kb_id, node_name, node_attrs):
    chunk = {
        "name_kwd": node_name,
        "important_kwd": [node_name],
        "title_tks": rag_tokenizer.tokenize(node_name),
        "content_with_weight": json.dumps({"name": node_name, **node_attrs}, ensure_ascii=False),
        "content_ltks": rag_tokenizer.tokenize(node_attrs["description"]),
        "knowledge_graph_kwd": "entity",
        "rank_int": node_attrs["rank"],
        "weight_int": node_attrs["weight"]

    }
    chunk["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(chunk["content_ltks"])

    expand_chunk(chunk, node_attrs.get('doc_id'), kb_id)
    return chunk


def build_graph_chunk(doc_id, node_name, **node_attrs):
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"knowledge_graph_kwd": "graph"}},
                    {"term": {"doc_id": doc_id}}
                ]
            }
        }
    }

    graph_json = ELASTICSEARCH.get_by_query(query)
    graph: nx.Graph = nx.node_link_graph(graph_json)
    graph.add_node(node_name, node_attrs)  # 新增或修改
    json.dumps(nx.node_link_data(graph))
    return {
        "content_with_weight": json.dumps(nx.node_link_data(graph), ensure_ascii=False, indent=2),
        "knowledge_graph_kwd": "graph"
    }


def expand_chunk(chunk, doc_id, kb_id):
    md5 = hashlib.md5()
    md5.update((chunk["content_with_weight"] +
                chunk.get('doc_id', str(uuid.uuid1()))).encode("utf-8"))
    # 每个chunk必须包含的
    chunk["_id"] = md5.hexdigest()
    chunk["create_time"] = str(datetime.datetime.now()).replace("T", " ")[:19]
    chunk["create_timestamp_flt"] = datetime.datetime.now().timestamp()
    # 每个chunk必须包含的
    chunk["doc_id"] = doc_id,
    chunk["kb_id"] = kb_id
