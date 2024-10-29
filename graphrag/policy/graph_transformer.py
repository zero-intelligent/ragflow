import json
import re
import networkx as nx
from lark import Lark, Transformer, v_args, Token, Tree
from rag.utils.es_conn import ELASTICSEARCH
from graphrag.policy.grammar import grammar
from loguru import logger as log


@v_args(inline=True)  # Affects the signatures of the methods
class NetWorkGraphTree(Transformer):
    
    def __init__(self,graph:nx.Graph):
        self.graph = graph 
    
    def start(self,exp:Token):
        return exp
    
    def exp(self, *args):
        return any(args)
        
    def and_exp(self, *args):
        return all(args)

    def not_exp(self, exp:Token|Tree):
        if isinstance(exp,Tree):
            term = exp.children[0]
            return not self.term(term.children)
        elif isinstance(exp,bool):
            return not exp
        else:
            raise Exception(f"unexpected type:{type(exp)}")
        
    def term(self,term:Token):
        if isinstance(term,dict):
            return term
        match(term.data.value):
            case "item_eq":
                return self.term_eq(*term.children)
            case "item_contains":
                return self.item_contains(*term.children)
            case "item_regexp":
                return self.item_regexp(*term.children)
            case _:
                return self.exp(*term.children)
            
    def term_eq(self, entity_type:Token, attr_or_value:Token, value:Token=None):
        entity_type = entity_type.strip("'")
        attr = (attr_or_value[1:] if value else "id").strip("'")
        value = (value or attr_or_value).strip("'")
        
        if ',' in str(value):
            values = value.split(',')
            return all([self.graph_query(entity_type,attr,value,'=') for value in values])
        else:
            return self.graph_query(entity_type,attr,value,'=')
    
    def graph_query(self,entity_type,attr,value,op='='):
        entity_type = str(entity_type).strip("'")
        attr = str(attr).strip("'")
        value = str(value).strip("'")
        
        for node,attr_dict in self.graph.nodes(data=True):
            if not attr_dict.get('entity_type') == entity_type:
                continue
            v = node if attr=='id' else attr_dict.get(attr)
            match(op):
                case "=" if v == value:
                    return True
                case "~" if value in v:
                    return True
                case "=~" if re.match(value,v):
                    return True
        return False
        
    def item_contains(self,entity_type:Token, attr_or_value:Token, value:Token=None):
        attr = attr_or_value[1:] if value else "id"
        value = value or attr_or_value
        return self.graph_query(entity_type,attr,value,'~')
        
    def item_regexp(self, entity_type:Token, attr_or_value:Token, value:Token=None):
        attr = attr_or_value[1:] if value else "id"
        value = value or attr_or_value
        return self.graph_query(entity_type,attr,value,'=~')
   
  

def graph_of_doc(index:str="ragflow_7d19a176807611efb0f80242ac120006",
                doc:str="aa610bd08c8111ef804c0242ac120003"):
    ELASTICSEARCH.idxnm = index
    q = {
        "query": {
            "bool": {
            "filter": [
                {
                "term": {
                    "knowledge_graph_kwd": "graph"
                }
                },
                {
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
                }
            ]
            }
        }
    }
    
    for hits in ELASTICSEARCH.scrollIter(q=q):
        for hit in hits:
            graph_json = hit['_source']['content_with_weight']
            node_link_data = json.loads(graph_json)
            graph = nx.node_link_graph(node_link_data)
            return graph
        

def evaluate_rule_on_network_graph(rules:str|list[str],doc:str):
    batch_result = {}
    if isinstance(rules,str):
        rules = [rules]

    # 获取稳定的图结构
    graph = graph_of_doc(doc=doc)
    if not graph:
        log.error(f"找不到文档:{doc}")
        return
    # 基于此图的策略引擎
    engine = Lark(grammar, parser="lalr", transformer=NetWorkGraphTree(graph)).parse
    
    for rule in rules:
        # 执行引擎，返回结果
        is_pass = engine(rule)
        log.info(f"run rule:【{rule}】,{"PASS" if is_pass else "NO_PASS"}")
        batch_result[rule] = is_pass
        
    return batch_result