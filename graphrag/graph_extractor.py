# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License
"""
Reference:
 - [graphrag](https://github.com/microsoft/graphrag)
"""

import logging
import numbers
import random
import time
import re
import traceback
from dataclasses import dataclass
from typing import Any, Mapping, Callable
import tiktoken
from graphrag import prompt_messages
from graphrag.graph_prompt import GRAPH_EXTRACTION_PROMPT, CONTINUE_PROMPT, LOOP_PROMPT
from graphrag.utils import ErrorHandlerFn, full_to_half, perform_variable_replacements, clean_str
from rag.llm.chat_model import Base as CompletionLLM
import networkx as nx
from rag.utils import build_sub_texts_2d, num_tokens_from_string
from timeit import default_timer as timer
from loguru import logger as log

DEFAULT_TUPLE_DELIMITER = "<|>"
DEFAULT_RECORD_DELIMITER = "##"
DEFAULT_COMPLETION_DELIMITER = "<|COMPLETE|>"
DEFAULT_ENTITY_TYPES = ["organization", "person", "location", "event", "time"]
ENTITY_EXTRACTION_MAX_GLEANINGS = 1


@dataclass
class GraphExtractionResult:
    """Unipartite graph extraction result class definition."""

    output: nx.Graph
    source_docs: dict[Any, Any]


class GraphExtractor:
    """Unipartite graph extractor class definition."""

    _llm: CompletionLLM
    _join_descriptions: bool
    _tuple_delimiter_key: str
    _record_delimiter_key: str
    _entity_types_key: str
    _input_text_key: str
    _completion_delimiter_key: str
    _entity_name_key: str
    _input_descriptions_key: str
    _extraction_prompt: str
    _summarization_prompt: str
    _loop_args: dict[str, Any]
    _max_gleanings: int
    _on_error: ErrorHandlerFn

    def __init__(
        self,
        llm_invoker: CompletionLLM,
        prompt: str | None = None,
        tuple_delimiter_key: str | None = None,
        record_delimiter_key: str | None = None,
        input_text_key: str | None = None,
        entity_types_key: str | None = None,
        completion_delimiter_key: str | None = None,
        join_descriptions=True,
        encoding_model: str | None = None,
        max_gleanings: int | None = None,
        on_error: ErrorHandlerFn | None = None,
    ):
        """Init method definition."""
        # TODO: streamline construction
        self._llm = llm_invoker
        self._join_descriptions = join_descriptions
        self._input_text_key = input_text_key or "input_text"
        self._tuple_delimiter_key = tuple_delimiter_key or "tuple_delimiter"
        self._record_delimiter_key = record_delimiter_key or "record_delimiter"
        self._completion_delimiter_key = (
            completion_delimiter_key or "completion_delimiter"
        )
        self._entity_types_key = entity_types_key or "entity_types"
        self._extraction_prompt = prompt or GRAPH_EXTRACTION_PROMPT
        self._max_gleanings = (
            max_gleanings
            if max_gleanings is not None
            else ENTITY_EXTRACTION_MAX_GLEANINGS
        )
        self._on_error = on_error or (lambda _e, _s, _d: None)
        self.prompt_token_count = num_tokens_from_string(self._extraction_prompt)

        # Construct the looping arguments
        encoding = tiktoken.get_encoding(encoding_model or "cl100k_base")
        yes = encoding.encode("YES")
        no = encoding.encode("NO")
        self._loop_args = {"logit_bias": {yes[0]: 100, no[0]: 100}, "max_tokens": 1}

    def build_chat_messages(self,chunks: list[str], entity_types: list[str]) -> dict:
        left_token_count = self._llm.max_length - self.prompt_token_count - 1024
        left_token_count = max(self._llm.max_length * 0.6, left_token_count)

        assert left_token_count > 0, f"The LLM context length({self._llm.max_length}) is smaller than prompt({self.prompt_token_count})"
        
        prompt_vars = prompt_messages.create_prompt_variables({"entity_types": entity_types})
        sub_texts_2d = build_sub_texts_2d(chunks, left_token_count)
        
        chat_id_messages = {}
        # 注意 阿里云通义千问 qwen-plus batch 模式 custom_id  只支持数字 custom_id， 他们答应2024.12 月前修复此问题
        for i, sub_text in enumerate(sub_texts_2d):
            chat_id_messages |= {f"graph_{i*1000+j}": prompt_messages.process(text, prompt_vars) for j, text in enumerate(sub_text)}
        return chat_id_messages
            
    
    def __call__(
        self, texts: list[str],
            prompt_variables: dict[str, Any] | None = None,
            callback: Callable | None = None,
            retry_cnt:int = 3
    ) -> GraphExtractionResult:
        """Call method definition."""
        if prompt_variables is None:
            prompt_variables = {}
        all_records: dict[int, str] = {}
        source_doc_map: dict[int, str] = {}

        # Wire defaults into the prompt variables
        prompt_variables = {
            **prompt_variables,
            self._tuple_delimiter_key:      prompt_variables.get(self._tuple_delimiter_key) or DEFAULT_TUPLE_DELIMITER,
            self._record_delimiter_key:     prompt_variables.get(self._record_delimiter_key) or DEFAULT_RECORD_DELIMITER,
            self._completion_delimiter_key: prompt_variables.get(self._completion_delimiter_key) or DEFAULT_COMPLETION_DELIMITER,
            self._entity_types_key: ",".join(
                prompt_variables.get(self._entity_types_key) or DEFAULT_ENTITY_TYPES
            ),
        }

        st = timer()
        total = len(texts)
        total_token_count = 0
        for doc_index, text in enumerate(texts):
            left_cnt = retry_cnt
            while left_cnt > 0:
                try:
                    # Invoke the entity extraction
                    result, token_count = self._process_document(text, prompt_variables)
                    source_doc_map[doc_index] = text
                    all_records[doc_index] = result
                    total_token_count += token_count
                    if callback: callback(msg=f"{doc_index+1}/{total}, elapsed: {timer() - st}s, used tokens: {total_token_count}")
                    time.sleep(random.random())
                    break
                except Exception as e:
                    if callback: callback(msg="Knowledge graph extraction error:{}".format(str(e)))
                    logging.exception("error extracting graph")
                    self._on_error(
                        e,
                        traceback.format_exc(),
                        {
                            "doc_index": doc_index,
                            "text": text,
                        },
                    )
                finally:
                    left_cnt -= 1

        output = self._process_results(
            all_records,
            prompt_variables.get(self._tuple_delimiter_key, DEFAULT_TUPLE_DELIMITER),
            prompt_variables.get(self._record_delimiter_key, DEFAULT_RECORD_DELIMITER),
        )

        return GraphExtractionResult(
            output=output,
            source_docs=source_doc_map,
        )

    def _process_document(
        self, text: str, prompt_variables: dict[str, str]
    ) -> str:
        variables = {
            **prompt_variables,
            self._input_text_key: text,
        }
        token_count = 0
        text = perform_variable_replacements(self._extraction_prompt, variables=variables)
        gen_conf = {
            "temperature": 0.3,
            "max_tokens": 40960
        }
        response = self._llm.chat(text, [{"role": "user", "content": "Output:"}], gen_conf)
        if response.find("**ERROR**") >=0: raise Exception(response)
        token_count = num_tokens_from_string(text + response)

        results = response or ""
        # history = [{"role": "system", "content": text}, {"role": "assistant", "content": response}]

        # Repeat to ensure we maximize entity count
        # for i in range(self._max_gleanings):
        #     text = perform_variable_replacements(CONTINUE_PROMPT, history=history, variables=variables)
        #     history.append({"role": "user", "content": text})
        #     response = self._llm.chat("", history, gen_conf)
        #     if response.find("**ERROR**") >=0: raise Exception(response)
        #     results += response or ""

        #     # if this is the final glean, don't bother updating the continuation flag
        #     if i >= self._max_gleanings - 1:
        #         break
        #     history.append({"role": "assistant", "content": response})
        #     history.append({"role": "user", "content": LOOP_PROMPT})
        #     continuation = self._llm.chat("", history, self._loop_args)
        #     if continuation != "YES":
        #         break

        return results, token_count

    def _process_results(
        self,
        results: dict[int, str],
        tuple_delimiter: str,
        record_delimiter: str,
    ) -> nx.Graph:
        """Parse the result string to create an undirected unipartite graph.

        Args:
            - results - dict of results from the extraction chain
            - tuple_delimiter - delimiter between tuples in an output record, default is '<|>'
            - record_delimiter - delimiter between records, default is '##'
        Returns:
            - output - unipartite graph in graphML format
        """
        graph = nx.Graph()
        for source_doc_id, extracted_data in results.items():
            records = [r.strip() for r in extracted_data.split(record_delimiter)]

            for record in records:
                record = re.sub(r"^\(|\)$", "", record.strip())
                record_attributes = record.split(tuple_delimiter)

                if record_attributes[0] == '"entity"' and len(record_attributes) >= 4:
                    # add this record as a node in the G
                    entity_name = clean_str(record_attributes[1].upper())
                    entity_type = clean_str(record_attributes[2].upper())
                    entity_description = clean_str(record_attributes[3])

                    if entity_name in graph.nodes():
                        node = graph.nodes[entity_name]
                        if self._join_descriptions:
                            node["description"] = "\n".join(
                                list({
                                    *_unpack_descriptions(node),
                                    entity_description,
                                })
                            )
                        else:
                            if len(entity_description) > len(node["description"]):
                                node["description"] = entity_description
                        node["source_id"] = ", ".join(
                            list({
                                *_unpack_source_ids(node),
                                str(source_doc_id),
                            })
                        )
                        node["entity_type"] = (
                            entity_type if entity_type != "" else node["entity_type"]
                        )
                    else:
                        graph.add_node(
                            entity_name,
                            entity_type=entity_type,
                            description=entity_description,
                            source_id=str(source_doc_id),
                            weight=1
                        )

                if (
                    record_attributes[0] == '"relationship"'
                    and len(record_attributes) >= 5
                ):
                    # add this record as edge
                    source = clean_str(record_attributes[1].upper())
                    target = clean_str(record_attributes[2].upper())
                    edge_description = clean_str(record_attributes[3])
                    edge_source_id = clean_str(str(source_doc_id))
                    weight = (
                        float(record_attributes[-1])
                        if isinstance(record_attributes[-1], numbers.Number)
                        else 1.0
                    )
                    if source not in graph.nodes():
                        graph.add_node(
                            source,
                            entity_type="",
                            description="",
                            source_id=edge_source_id,
                            weight=1
                        )
                    if target not in graph.nodes():
                        graph.add_node(
                            target,
                            entity_type="",
                            description="",
                            source_id=edge_source_id,
                            weight=1
                        )
                    if graph.has_edge(source, target):
                        edge_data = graph.get_edge_data(source, target)
                        if edge_data is not None:
                            weight += edge_data["weight"]
                            if self._join_descriptions:
                                edge_description = "\n".join(
                                    list({
                                        *_unpack_descriptions(edge_data),
                                        edge_description,
                                    })
                                )
                            edge_source_id = ", ".join(
                                list({
                                    *_unpack_source_ids(edge_data),
                                    str(source_doc_id),
                                })
                            )
                    graph.add_edge(
                        source,
                        target,
                        weight=weight,
                        description=edge_description,
                        source_id=edge_source_id,
                    )

        for node_degree in graph.degree:
            graph.nodes[str(node_degree[0])]["rank"] = int(node_degree[1])
        return graph




    def process_results(
            results: dict[str, str],
            tuple_delimiter: str,
            record_delimiter: str,
    ) -> nx.Graph:
        """Parse the result string to create an undirected unipartite graph.

        Args:
            - results - dict of results from the extraction chain
            - tuple_delimiter - delimiter between tuples in an output record, default is '<|>'
            - record_delimiter - delimiter between records, default is '##'
        Returns:
            - output - unipartite graph in graphML format
        """
        graph = nx.Graph()
        for source_doc_id, extracted_data in results.items():
            records = [r.strip() for r in extracted_data.split(record_delimiter)]

            for record in records:
                record = re.sub(r"^\(|\)$", "", record.strip())
                record_attributes = record.split(tuple_delimiter)

                if record_attributes[0] == '"entity"' and len(record_attributes) >= 4:
                    # add this record as a node in the G
                    entity_name = clean_str(record_attributes[1].upper())
                    entity_name = full_to_half(entity_name)
                    
                    entity_type = clean_str(record_attributes[2].upper())
                    entity_type = full_to_half(entity_type)
                    entity_description = clean_str(record_attributes[3])
                    
                    if entity_name == entity_type:
                        continue
                    if not entity_name \
                        or not entity_type \
                        or not re.match(r'([^\s()]+(?:\s+[^\s()]+)*)(?:\s*\(([^)]+)\))',entity_name) \
                        or not re.match(r'([^\s()]+(?:\s+[^\s()]+)*)(?:\s*\(([^)]+)\))',entity_type):
                        log.info(f"'{entity_type}' or '{entity_name}' invalid (空，相等，不满足英文名称（中文名称）格式) in '{record}', so out of graph")
                        continue

                    if entity_name in graph.nodes():
                        node = graph.nodes[entity_name]
                        if True:
                            node["description"] = "\n".join(
                                list({
                                    *_unpack_descriptions(node),
                                    entity_description,
                                })
                            )
                        else:
                            if len(entity_description) > len(node["description"]):
                                node["description"] = entity_description
                        node["source_id"] = ", ".join(
                            list({
                                *_unpack_source_ids(node),
                                str(source_doc_id),
                            })
                        )
                        node["entity_type"] = (
                            entity_type if entity_type != "" else node["entity_type"]
                        )
                    else:
                        graph.add_node(
                            entity_name,
                            entity_type=entity_type,
                            description=entity_description,
                            source_id=str(source_doc_id),
                            weight=1
                        )

                if (
                        record_attributes[0] == '"relationship"'
                        and len(record_attributes) >= 5
                ):
                    # add this record as edge
                    source = clean_str(record_attributes[1].upper())
                    target = clean_str(record_attributes[2].upper())
                    edge_description = clean_str(record_attributes[3])
                    edge_source_id = clean_str(str(source_doc_id))
                    weight = (
                        float(record_attributes[-1])
                        if isinstance(record_attributes[-1], numbers.Number)
                        else 1.0
                    )
                    if source not in graph.nodes():
                        graph.add_node(
                            source,
                            entity_type="",
                            description="",
                            source_id=edge_source_id,
                            weight=1
                        )
                    if target not in graph.nodes():
                        graph.add_node(
                            target,
                            entity_type="",
                            description="",
                            source_id=edge_source_id,
                            weight=1
                        )
                    if graph.has_edge(source, target):
                        edge_data = graph.get_edge_data(source, target)
                        if edge_data is not None:
                            weight += edge_data["weight"]
                            if True:
                                edge_description = "\n".join(
                                    list({
                                        *_unpack_descriptions(edge_data),
                                        edge_description,
                                    })
                                )
                            edge_source_id = ", ".join(
                                list({
                                    *_unpack_source_ids(edge_data),
                                    str(source_doc_id),
                                })
                            )
                    graph.add_edge(
                        source,
                        target,
                        weight=weight,
                        description=edge_description,
                        source_id=edge_source_id,
                    )

        for node_degree in graph.degree:
            graph.nodes[str(node_degree[0])]["rank"] = int(node_degree[1])
        return graph

def _unpack_descriptions(data: Mapping) -> list[str]:
    value = data.get("description", None)
    return [] if value is None else value.split("\n")


def _unpack_source_ids(data: Mapping) -> list[str]:
    value = data.get("source_id", None)
    return [] if value is None else value.split(", ")



