# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License
"""
Reference:
 - [graphrag](https://github.com/microsoft/graphrag)
"""

import json
import logging
import os
import re
import traceback
from dataclasses import dataclass
from typing import Any, List, Callable
import networkx as nx
import pandas as pd
from graphrag import leiden
from graphrag.community_report_prompt import COMMUNITY_REPORT_PROMPT
from graphrag.leiden import add_community_info2graph
from rag.llm.batch_model import BatchModel
from rag.llm.chat_model import Base as CompletionLLM
from graphrag.utils import ErrorHandlerFn, perform_variable_replacements, dict_has_keys_with_types,file_cache
from rag.utils import num_tokens_from_string
from timeit import default_timer as timer

log = logging.getLogger(__name__)


@dataclass
class CommunityReportsResult:
    """Community reports result class definition."""

    output: List[str]
    structured_output: List[dict]


class CommunityReportsExtractor:
    """Community reports extractor class definition."""

    _llm: CompletionLLM
    _extraction_prompt: str
    _output_formatter_prompt: str
    _on_error: ErrorHandlerFn
    _max_report_length: int

    def __init__(
        self,
        llm_invoker: CompletionLLM,
        extraction_prompt: str | None = None,
        on_error: ErrorHandlerFn | None = None,
        max_report_length: int | None = None,
    ):
        """Init method definition."""
        self._llm = llm_invoker
        self._extraction_prompt = extraction_prompt or COMMUNITY_REPORT_PROMPT
        self._on_error = on_error or (lambda _e, _s, _d: None)
        self._max_report_length = max_report_length or 1500

    def build_chat_messages(self,graph:nx.Graph):
        communities: dict[str, dict[str, List]] = leiden.run(graph, {})
        relations_df = pd.DataFrame([{"source":s, "target": t, **attr} for s, t, attr in graph.edges(data=True)])
        result = {}
        for level, comm in communities.items():
            for cm_id, gents in comm.items():
                ents = gents["nodes"]
                ent_df = pd.DataFrame([{"entity": n, **graph.nodes[n]} for n in ents])
                rela_df = relations_df[(relations_df["source"].isin(ents)) | (relations_df["target"].isin(ents))].reset_index(drop=True)
                prompt_variables = {
                    "entity_df": ent_df.to_csv(index_label="id"),
                    "relation_df": rela_df.to_csv(index_label="id")
                }
                id = f"community-{level}-{cm_id}"
                text = perform_variable_replacements(self._extraction_prompt, variables=prompt_variables)
                result[id] = (text,gents)
                
        return result
        
    @file_cache
    def __call__(self, graph: nx.Graph, callback: Callable | None = None):
        chat_inputs = self.build_chat_messages(graph)
        token_count = 0
        st = timer()
        if os.environ.get('BatchMode',"").lower() == "online":
            def online_chat(text):
                try:
                    response = self._llm.chat(text, [{"role": "user", "content": "Output:"}], {"temperature": 0.3})
                    nonlocal token_count
                    token_count += num_tokens_from_string(text + response)
                except Exception as e:
                    print("ERROR: ", traceback.format_exc())
                    self._on_error(e, traceback.format_exc(), None)
                    return None
            st = timer()
            chat_results = {id: online_chat(text) for id,(text,_) in chat_inputs.items()}
        else:
            log.info(f"batching community report.id_message cnt:{len(chat_inputs)}")
            batch_llm = BatchModel(model_instance = self._llm.mdl)
            chat_results = batch_llm.batch_api_call({id:[{"role":"system","content":text},
                                                         {"role":"user","content":"Output:"}]
                                                     for id,(text,_) in chat_inputs.items()})
            
        if callback: 
                callback(msg=f"batch_mode: {os.environ.get('BatchModel',True)} Communities: {len(chat_inputs)}, elapsed: {timer() - st}s, used tokens: {token_count}")
                
        res_str,res_dict = [],[]
        for id,response in chat_results.items():
            response = re.sub(r"^[^\{]*", "", response)
            response = re.sub(r"[^\}]*$", "", response)
            response = re.sub(r'(?<!")\n(?!")','',response)
            response = response.replace("\\'", "'")
            if not response:
                continue
            try:
                response = json.loads(response)
            except Exception as ex:
                log.warning(f"json resolve fail {str(ex)},json:{response}")
                continue
                
            if not dict_has_keys_with_types(response, [
                            ("title", str),
                            ("summary", str),
                            ("findings", list),
                            ("rating", float),
                            ("rating_explanation", str),
                        ]): 
                continue
            response["weight"] = chat_inputs[id][1]["weight"]
            response["entities"] = chat_inputs[id][1]["nodes"]
            add_community_info2graph(graph, response["entities"], response["title"])
            res_str.append(self._get_text_output(response))
            res_dict.append(response)
            
            
        return CommunityReportsResult(
            structured_output=res_dict,
            output=res_str,
        )

    def _get_text_output(self, parsed_output: dict) -> str:
        title = parsed_output.get("title", "Report")
        summary = parsed_output.get("summary", "")
        findings = parsed_output.get("findings", [])

        def finding_summary(finding: dict):
            if isinstance(finding, str):
                return finding
            return finding.get("summary")

        def finding_explanation(finding: dict):
            if isinstance(finding, str):
                return ""
            return finding.get("explanation")

        report_sections = "\n\n".join(
            f"## {finding_summary(f)}\n\n{finding_explanation(f)}" for f in findings
        )
     
        return f"# {title}\n\n{summary}\n\n{report_sections}"
