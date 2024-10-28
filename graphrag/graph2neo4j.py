from typing import List
from graphrag.db.neo4j import driver
import networkx as nx
from loguru import logger as log

def graph2neo4j(graph:nx.Graph,nodeLabel_attr:List[str] = ['entity_type']):
    """
    将当前的 python 里的 nx.Graph 里的数据同步到 neo4j ;
    确保节点的属性和关系的属性全部同步过去,节点的属性和关系的属性schema是未知的;
    如果和 neo4j 中现有的 node 和 relation 有冲突，则要融合进现有的节点。
    """
    if not nodeLabel_attr:
        log.error(f"nodeLabel_attr shouldn't be empty")
        return
    if not graph:
        log.error(f"graph shouldn't be None")
        return
    
    with driver.session() as session:
        # 创建或融合节点
        for node, attrs in graph.nodes(data=True):
            labels = [":" + attrs.pop(attr) for attr in nodeLabel_attr]
            label_str = "".join(labels) if labels else ''
            node_properties = {**attrs, 'id': node}
            session.run(f"""
                MERGE (n{label_str} {{id: $id}})
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
            
    log.info(f"{len(graph.nodes(data=True))} nodes, {len(graph.edges(data=True))} edges import to neo4j.")