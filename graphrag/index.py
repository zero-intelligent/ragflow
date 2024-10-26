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
import time
from functools import reduce
from typing import List

import networkx as nx

from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from api.db.services.user_service import TenantService
from graphrag import openai_batch, prompt_messages, graph_extractor
from graphrag.community_reports_extractor import CommunityReportsExtractor
from graphrag.entity_resolution import EntityResolution
from graphrag.graph_extractor import GraphExtractor
from graphrag.mind_map_extractor import MindMapExtractor
from graphrag.prompt_messages import DEFAULT_TUPLE_DELIMITER, DEFAULT_RECORD_DELIMITER, DEFAULT_TUPLE_DELIMITER_KEY, \
    DEFAULT_RECORD_DELIMITER_KEY
from rag.nlp import rag_tokenizer
from rag.utils import num_tokens_from_string

import sys
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


def build_sub_texts_2d(chunks: List[str], left_token_count):
    BATCH_SIZE = 4
    texts, sub_texts, graphs = [], [], []
    cnt = 0

    for i in range(len(chunks)):
        tkn_cnt = num_tokens_from_string(chunks[i])
        if cnt + tkn_cnt >= left_token_count and texts:
            for b in range(0, len(texts), BATCH_SIZE):
                sub_texts.append(texts[b:b + BATCH_SIZE])

            texts = []
            cnt = 0
        texts.append(chunks[i])
        cnt += tkn_cnt
    if texts:
        for b in range(0, len(texts), BATCH_SIZE):
            sub_texts.append(texts[b:b + BATCH_SIZE])

    return sub_texts


def build_line(custom_id, content, prompt_vars):
    data = {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "qwen-plus",
            "messages": prompt_messages.process(content, prompt_vars)
        }
    }

    return json.dumps(data, ensure_ascii=False)


def build_knowlege_graph_chunks(tenant_id: str, chunks: List[str], callback,
                                entity_types=["organization", "person", "location", "event", "time"]):
    _, tenant = TenantService.get_by_id(tenant_id)
    llm_bdl = LLMBundle(tenant_id, LLMType.CHAT, tenant.llm_id)
    ext = GraphExtractor(llm_bdl)
    left_token_count = llm_bdl.max_length - ext.prompt_token_count - 1024
    left_token_count = max(llm_bdl.max_length * 0.6, left_token_count)

    assert left_token_count > 0, f"The LLM context length({llm_bdl.max_length}) is smaller than prompt({ext.prompt_token_count})"

    sub_texts_2d = build_sub_texts_2d(chunks, left_token_count)

    log.info(f"########## sub_texts_2d={sub_texts_2d}")

    ccids = []
    lines = []
    prompt_vars = prompt_messages.create_prompt_variables({"entity_types": entity_types})
    for i, sub_text in enumerate(sub_texts_2d):
        cids = []
        for j, line in enumerate(sub_text):
            cid = (i * 1000) + j  # i + "-" + j
            cids.append(cid)
            lines.append(build_line(cid, line, prompt_vars))

        ccids.append(cids)

    log.info(f"########## ccids={ccids}")
    log.info(f"########## lines={lines}")

    f_name = str(time.time_ns()) + ".txt"
    log.info(f"########## f_name={f_name}")

    inputs_dir = os.path.join(os.getcwd(), 'inputs')
    os.makedirs(inputs_dir, exist_ok=True)
    openai_batch.write_file("\n".join(lines), f_name, inputs_dir)

    fid = openai_batch.file_upload(os.path.join(inputs_dir, f_name))
    log.info(f"########## fid={fid}")

    bid = openai_batch.batch_create(fid)
    log.info(f"########## bid={bid}")

    chat_results = []
    while True:
        time.sleep(60)
        batch = openai_batch.query(bid)
        log.info(f"#### batch query ###### bid={bid},status:{batch.status}")
        if batch.status == 'completed':
            chat_results = openai_batch.get_results(batch.id)
            break
        elif batch.status in ['failed','expired','cancelling','cancelled']:
            raise ValueError(batch)

    idxed_chat_results: dict[int, str] = {}
    for chat_result in chat_results:
        idxed_chat_results[chat_result['id']] = chat_result['content']

    log.info(f"########## idxed_chat_results={idxed_chat_results}")

    ordered_chat_results = []
    for cids in ccids:
        tmp = {}
        for cid in cids:
            tmp[cid] = idxed_chat_results[str(cid)]
        ordered_chat_results.append(tmp)

    log.info(f"########## ordered_chat_results={ordered_chat_results}")

    outputs = [graph_extractor.GraphExtractor.process_results(chat_result,
                                                              prompt_vars.get(DEFAULT_TUPLE_DELIMITER_KEY,
                                                                              DEFAULT_TUPLE_DELIMITER),
                                                              prompt_vars.get(DEFAULT_RECORD_DELIMITER_KEY,
                                                                              DEFAULT_RECORD_DELIMITER)
                                                              )
               for chat_result in ordered_chat_results]

    callback(0.5, "Extracting entities.")
    graphs = []
    for i, output in enumerate(outputs):
        graphs.append(output)

    graph = reduce(graph_merge, graphs) if graphs else nx.Graph()
    er = EntityResolution(llm_bdl)
    graph = er(graph).output

    _chunks = chunks
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

    callback(0.75, "Extracting mind graph.")
    mindmap = MindMapExtractor(llm_bdl)
    mg = mindmap(_chunks).output
    if not len(mg.keys()): return chunks

    print(json.dumps(mg, ensure_ascii=False, indent=2))
    chunks.append(
        {
            "content_with_weight": json.dumps(mg, ensure_ascii=False, indent=2),
            "knowledge_graph_kwd": "mind_map"
        })

    return chunks
