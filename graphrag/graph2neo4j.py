from typing import List
from graphrag.db.neo4j import driver
import networkx as nx
from loguru import logger as log

def graph2neo4j(graph: nx.Graph, nodeLabel_attr: List[str] = ['entity_type']):
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
    
    max_node_name_length = 30
    
    with driver.session() as session:
        # 批量创建或融合节点
        node_queries = []
        for node, attrs in graph.nodes(data=True):
            if len(node) > max_node_name_length:
                log.error(f"node name '{node}' too long, abandon importing to neo4j")
                continue
            labels = [f':`{attrs[attr]}`' for attr in nodeLabel_attr if attrs.get(attr)]
            label_str = "".join(labels) if labels else ''
            node_properties = ', '.join([f"{k}: '{v}'" for k, v in attrs.items()])
            node_queries.append(f"""
                MERGE (n{label_str} {{id: '{node}'}})
                ON CREATE SET n += {{{node_properties}}}
                ON MATCH SET n += {{{node_properties}}}
            """)

        # 批量创建或融合边
        edge_queries = []
        for source, target, attrs in graph.edges(data=True):
            if len(source) > max_node_name_length:
                log.error(f"node name '{node}' too long, abandon importing to neo4j")
                continue
            if len(target) > max_node_name_length:
                log.error(f"node name '{target}' too long, abandon importing to neo4j")
                continue
            
            edge_properties = ', '.join([f"{k}: '{v}'" for k, v in attrs.items()])
            edge_queries.append(f"""
                MATCH (a:Node {{id: '{source}'}}), (b:Node {{id: '{target}'}})
                MERGE (a)-[r:CONNECTED_TO]->(b)
                ON CREATE SET r += {{{edge_properties}}}
                ON MATCH SET r += {{{edge_properties}}}
            """)

        # 执行节点的批量查询
        if node_queries:
            node_query_string = "CALL { " + " UNION ALL ".join(node_queries) + " }"
            session.run(node_query_string)

        # 执行边的批量查询
        if edge_queries:
            edge_query_string = "CALL { " + " UNION ALL ".join(edge_queries) + " }"
            session.run(edge_query_string)

    log.info(f"{len(graph.nodes(data=True))} nodes, {len(graph.edges(data=True))} edges imported to neo4j.")
