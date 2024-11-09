from collections import defaultdict
import json
from typing import List
import time
import fire
from graphrag.db import driver
import networkx as nx
from loguru import logger as log
from rag.utils.es_conn import ELASTICSEARCH
from graphrag.utils import escape, file_cache

@file_cache
def graph2neo4j(graph: nx.Graph, nodeLabel_attr: List[str] = ['entity_type']):
    do_graph2neo4j(graph,nodeLabel_attr)
    
def do_graph2neo4j(graph: nx.Graph, nodeLabel_attr: List[str] = ['entity_type']):
    """
    将当前的 python 里的 nx.Graph 里的数据同步到 neo4j ;
    确保节点的属性和关系的属性全部同步过去,节点的属性和关系的属性schema是未知的;
    如果和 neo4j 中现有的 node 和 relation 有冲突，则要融合进现有的节点。
    """
    if not nodeLabel_attr:
        log.error("nodeLabel_attr shouldn't be empty")
        return
    if not graph:
        log.error("graph shouldn't be None")
        return
    
    with driver.session() as session:
        # 批量创建或融合节点
        node_queries = []
        nodes_dict = defaultdict(int)
        for node, attrs in graph.nodes(data=True):
            labels = [f':`{escape(attrs[attr])}`' for attr in nodeLabel_attr if attrs.get(attr)]
            label_str = "".join(labels) if labels else ''
            nodes_dict[label_str] += 1
            node_properties = ', '.join([f"{k}: {"'" + escape(v) + "'"  if isinstance(v, str) else v}" for k, v in attrs.items()])
            node_queries.append(f"""
                MERGE (n{label_str} {{id: '{escape(node)}'}})
                ON CREATE SET n += {{{node_properties}}}
                ON MATCH SET n += {{{node_properties}}}
            """)
        log.info(f"importing nodes {nodes_dict}.")
        # 批量创建或融合边
        edge_queries = []
        for source, target, attrs in graph.edges(data=True):
            
            edge_properties = ', '.join([f"{k}: '{escape(v)}'" for k, v in attrs.items()])
            edge_queries.append(f"""
                MATCH (a {{id: '{escape(source)}'}}), (b {{id: '{escape(target)}'}})
                MERGE (a)-[r:CONNECTED_TO]-(b)
                ON CREATE SET r += {{{edge_properties}}}
                ON MATCH SET r += {{{edge_properties}}}
            """)

        BATCH_SIZE = 32
        start = time.time()
        # 执行节点的批量
        if node_queries:
            log.info(f"importing {len(node_queries)} nodes to neo4j")
            batchs = [node_queries[i:i + BATCH_SIZE] for i in range(0, len(node_queries), BATCH_SIZE)]
            for batch in batchs:
                node_query_string = "CALL() { " + " UNION ALL ".join(batch) + " } RETURN 1"
                result = session.run(node_query_string)
                summary = result.consume()
                log.info(f"{summary.counters.nodes_created} nodes created,{summary.counters.relationships_created} edges created,{summary.counters.properties_set} properties set,{summary.result_available_after/1000:.2f} s")

        log.info(f"{len(node_queries)} nodes imported to neo4j, last:{time.time()-start:.2f}s")
        
        start = time.time()
        # 执行边的批量
        if edge_queries:
            log.info(f"importing {len(edge_queries)} edges to neo4j")
            batchs = [edge_queries[i:i + BATCH_SIZE] for i in range(0, len(edge_queries), BATCH_SIZE)]
            for batch in batchs:
                edge_query_string = "CALL() { " + " UNION ALL ".join(batch) + " } RETURN 1"
                result = session.run(edge_query_string)
                summary = result.consume()
                log.info(f"{summary.counters.nodes_created} nodes created,{summary.counters.relationships_created} edges created,{summary.counters.properties_set} properties set,{summary.result_available_after/1000:.2f} s")
            
        log.info(f"{len(edge_queries)} edges imported to neo4j, last:{time.time()-start:.2f}s")
        
        # session 不会主动关闭，需要手动关闭
        driver.close()

def sync(index:str="ragflow_7d19a176807611efb0f80242ac120006",
         kb_id:str="fb7c4312973b11ef88ed0242ac120006",
         doc:str=None,
         uisng_cache:bool = False):
    
    query = {
        "query": {
            "bool": {
            "filter": [{
                    "term": {
                        "knowledge_graph_kwd": "graph"
                    }
                },
                {
                    "term": {
                        "kb_id": kb_id
                    }
                }
            ]
            }
        }
    }
    
    if doc:
        query['query']['bool']['filter'] += [{
                "bool": {
                    "should": [
                    {
                        "term": {
                            "doc_id": doc
                        }
                    },
                    {
                        "term": {
                            "docnm_kwd": doc
                        }
                    }
                ]
            }
        }]
        
    ELASTICSEARCH.idxnm = index
    
    for hits in ELASTICSEARCH.scrollIter(q=query):
        for hit in hits:
            log.info(f"processing graph of doc:{hit['_source']["docnm_kwd"]}")
            graph_json = hit['_source']['content_with_weight']
            node_link_data = json.loads(graph_json)
            graph = nx.node_link_graph(node_link_data)
            
            if uisng_cache:
                graph2neo4j(graph)
            else:
                do_graph2neo4j(graph)
      
if __name__ == "__main__":
    fire.Fire() # 自动加载模块方法，作为命令行参数