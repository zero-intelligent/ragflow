from lark import Lark, Transformer, v_args, Token, Tree
from graphrag.policy.grammar import grammar
from graphrag.db.neo4j import driver
from loguru import logger as log


@v_args(inline=True)  # Affects the signatures of the methods
class Neo4jCyberSyntaxTree(Transformer):
    
    def start(self,exp:Token):
        return f"match {exp['match']} \nwhere {exp['where']} \nreturn {exp['return']} limit 1\n"
    
    def exp(self, *args):
        return {
                "match":",".join([r['match'] for r in args]),
                "where":" or ".join([f"({r['where']})" for r in args]),
                "return":",".join([r['return'] for r in args])
            }
        
    def and_exp(self, *args):
        return {
            "match":",".join([r['match'] for r in args]),
            "where":" and ".join([f"({r['where']})" for r in args]),
            "return":",".join([r['return'] for r in args])
        }

    def not_exp(self, exp:Token|Tree):
        
        if isinstance(exp,Tree):
            term = exp.children[0]
            term_result = self.term(term.children)
            return {
                "match": term_result['match'],
                "where": f"not ({term_result['where']})",
                "return": term_result["return"]
            }
        elif isinstance(exp,dict):
            return {
                "match": exp['match'],
                "where": f"not ({exp['where']})",
                "return": exp["return"]
            }
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
        '''
        多值情况，参考代码：
        WITH ['Alice', 'Bob', 'Charlie'] AS names
        MATCH (p:Person)
        WHERE p.name IN names
        WITH COLLECT(p.name) AS foundNames, names
        RETURN ALL(name IN names WHERE name IN foundNames) AS allExist
        '''
        entity_type = entity_type.strip("'")
        attr = (attr_or_value[1:] if value else "id").strip("'")
        value = (value or attr_or_value).strip("'")
        var = value
        
        if ',' in str(value):
            values = value.split(',')
            matchs = [f"({value}:{entity_type} {{{attr}:'{value}'}})" for value in values]
            returns = [f"count({var})>0 as {var}" for var in values]
            return {
                "match":",".join(matchs),
                "where":"1=1",
                "return":",".join(returns)
            }
        else:
            return self.cyber_query(var,entity_type,attr,value,'=')
    
    def cyber_query(self,var,entity_type,attr,value,op='='):
        var = str(var).strip("'")
        entity_type = str(entity_type).strip("'")
        attr = str(attr).strip("'")
        value = str(value).strip("'")
        return {
                "match":f"({var}:{entity_type})",
                "where":f"{var}.{attr} {op} '{value}'",
                "return":f"count({var}) > 0 as {var}"
            }
        
    def item_contains(self,entity_type:Token, attr_or_value:Token, value:Token=None):
        attr = attr_or_value[1:] if value else "id"
        value = value or attr_or_value
        var = value
        return self.cyber_query(var,entity_type,attr,value,'contains')
        
    def item_regexp(self, entity_type:Token, attr_or_value:Token, value:Token=None):
        attr = attr_or_value[1:] if value else "id"
        value = value or attr_or_value
        var = value
        return self.cyber_query(var,entity_type,attr,value,'=~')
   
rule_engine_on_neo4j = Lark(grammar, parser="lalr", transformer=Neo4jCyberSyntaxTree()).parse



def evaluate_rule_on_neo4j(rules:str|list[str]):
    batch_result = {}
    if isinstance(rules,str):
        rules = [rules]
    with driver.session() as session:
        for rule in rules:
            # 执行引擎，返回 neo4j 查询语句
            cyper_query = rule_engine_on_neo4j(rule)
            
            #执行 cyber_query ，从数据库中返回结果
            result = list(session.run(cyper_query))
            
            # 确保每行每列都返回真 才算通过
            is_pass = all([all(record.values()) for record in result])
            
            log.info(f"run rule:【{rule}】,{"PASS" if is_pass else "NO_PASS"}")
            batch_result[rule] = is_pass
            
    return batch_result