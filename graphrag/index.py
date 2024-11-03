#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import json
import os
from functools import reduce
from typing import List

import networkx as nx

from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from api.db.services.user_service import TenantService
from graphrag import prompt_messages, graph_extractor
from graphrag.community_reports_extractor import CommunityReportsExtractor
from graphrag.entity_resolution import EntityResolution
from graphrag.graph2neo4j import graph2neo4j
from graphrag.graph_extractor import GraphExtractor
from graphrag.mind_map_extractor import MindMapExtractor
from graphrag.prompt_messages import DEFAULT_TUPLE_DELIMITER, DEFAULT_RECORD_DELIMITER, DEFAULT_TUPLE_DELIMITER_KEY, DEFAULT_RECORD_DELIMITER_KEY
from rag.llm.batch_model import BatchModel
from rag.nlp import rag_tokenizer
from rag.utils import build_sub_texts_2d
from loguru import logger as log


def graph_merge(g1, g2):
    g = g2.copy()
    for n, attr in g1.nodes(data=True):
        if n not in g2.nodes():
            g.add_node(n, **attr)
            continue

        g.nodes[n]["weight"] += 1
        if g.nodes[n]["description"].lower().find(attr["description"][:32].lower()) < 0:
            g.nodes[n]["description"] += "\n" + attr["description"]

    for source, target, attr in g1.edges(data=True):
        if g.has_edge(source, target):
            g[source][target].update({"weight": attr["weight"] + 1})
            continue
        g.add_edge(source, target, **attr)

    for node_degree in g.degree:
        g.nodes[str(node_degree[0])]["rank"] = int(node_degree[1])
    return g

    
def graph2chunks(graph:nx.Graph,chunks: List[str], llm_bdl:LLMBundle,callback):
    chunks = []
    for n, attr in graph.nodes(data=True):
        if attr.get("rank", 0) == 0:
            print(f"Ignore entity: {n}")
            continue
        chunk = {
            "name_kwd": n,
            "important_kwd": [n],
            "title_tks": rag_tokenizer.tokenize(n),
            "content_with_weight": json.dumps({"name": n, **attr}, ensure_ascii=False),
            "content_ltks": rag_tokenizer.tokenize(attr["description"]),
            "knowledge_graph_kwd": "entity",
            "rank_int": attr["rank"],
            "weight_int": attr["weight"]
        }
        chunk["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(chunk["content_ltks"])
        chunks.append(chunk)

    callback(0.6, "Extracting community reports.")
    cr = CommunityReportsExtractor(llm_bdl)
    cr = cr(graph, callback=callback)
    for community, desc in zip(cr.structured_output, cr.output):
        chunk = {
            "title_tks": rag_tokenizer.tokenize(community["title"]),
            "content_with_weight": desc,
            "content_ltks": rag_tokenizer.tokenize(desc),
            "knowledge_graph_kwd": "community_report",
            "weight_flt": community["weight"],
            "entities_kwd": community["entities"],
            "important_kwd": community["entities"]
        }
        chunk["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(chunk["content_ltks"])
        chunks.append(chunk)

    chunks.append(
        {
            "content_with_weight": json.dumps(nx.node_link_data(graph), ensure_ascii=False, indent=2),
            "knowledge_graph_kwd": "graph"
        })
    return chunks
    
def mind_map2chunk(mind_map: dict):
    return [{
            "content_with_weight": json.dumps(mind_map, ensure_ascii=False, indent=2),
            "knowledge_graph_kwd": "mind_map"
    }]

    
def build_knowlege_graph_chunks(tenant_id: str, filename:str,chunks: List[str], callback,
                                entity_types=["organization", "person", "location", "event", "time"]):
    _, tenant = TenantService.get_by_id(tenant_id)
    llm_bdl = LLMBundle(tenant_id, LLMType.CHAT, tenant.llm_id)
    graph_ext = GraphExtractor(llm_bdl)
    mind_map_ext = MindMapExtractor(llm_bdl)
    
    if os.environ.get('BatchMode',"").lower() == "online":
        left_token_count = llm_bdl.max_length - graph_ext.prompt_token_count - 1024
        left_token_count = max(llm_bdl.max_length * 0.6, left_token_count)

        assert left_token_count > 0, f"The LLM context length({llm_bdl.max_length}) is smaller than prompt({graph_ext.prompt_token_count})"
        
        sub_texts_2d = build_sub_texts_2d(chunks, left_token_count)
        graphs = [graph_ext(["\n".join(texts)], {"entity_types": entity_types}, callback).output for texts in sub_texts_2d]
        graph = reduce(graph_merge, graphs) if graphs else nx.Graph()
        mind_map_result = mind_map_ext(chunks).output
    else:
        log.info(f"batching {filename} on {llm_bdl.llm_name}")
        chat_id_messages = graph_ext.build_chat_messages(chunks,entity_types)
        chat_id_messages |= mind_map_ext.build_chat_messages(chunks)
        
        batch_llm = BatchModel(model_instance = llm_bdl.mdl)
        chat_results = batch_llm.batch_api_call(chat_id_messages)
        graph_chat_results = {f"{filename}-{k}":v for k,v in chat_results.items() if k.startswith('graph_')}

        prompt_vars = prompt_messages.create_prompt_variables({"entity_types": entity_types})
        graph = graph_extractor.GraphExtractor.process_results(
            results = graph_chat_results ,
            tuple_delimiter = prompt_vars.get(DEFAULT_TUPLE_DELIMITER_KEY,DEFAULT_TUPLE_DELIMITER),
            record_delimiter = prompt_vars.get(DEFAULT_RECORD_DELIMITER_KEY,DEFAULT_RECORD_DELIMITER)
        )
        
        mind_map_chat_results = {f"{filename}-{k}":v for k,v in chat_results.items() if k.startswith('mind_')}
        mind_map_result = mind_map_ext.responses2result(mind_map_chat_results).output

    callback(0.5, "Extracting entities.")
    er = EntityResolution(llm_bdl)
    graph = er(graph).output
    
    #将图导入neo4j
    graph2neo4j(graph)
    
    graph_chunks = graph2chunks(graph,chunks,llm_bdl,callback)
    mind_map_chunks = mind_map2chunk(mind_map_result)
    
    log.info(f"{filename} build_knowlege_graph_chunks completed.")
    return graph_chunks + mind_map_chunks

    