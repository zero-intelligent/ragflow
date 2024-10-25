import sys
import yaml
import glob
from pathlib import Path
from loguru import logger as log
from lark import Lark, Transformer, v_args, Token, Tree
from graphrag.db.neo4j import driver


grammar = r"""
    start: exp | not_exp

    exp: and_exp ("or" and_exp)*  // "or" 连接多个 and_exp
    and_exp: term ("and" term)*  // "and" 优先于 "or"
    not_exp: "not" term          // "not" 修饰一个表达式            
    term: item_eq
        | item_contains              
        | item_regexp   
        | "(" exp ")"
    item_eq: ENTITY_TYPE ENTITY_ATTRIBUTE? "=" ENTITY_ATTRIBUTE_VALUE ("," ENTITY_ATTRIBUTE_VALUE)*  // 实体属性值等于，如果多个值，中间用‘，’分开
    item_contains: ENTITY_TYPE ENTITY_ATTRIBUTE? "~" ENTITY_ATTRIBUTE_VALUE  // 实体属性值包含字符, 属性可以为空
    item_regexp: ENTITY_TYPE ENTITY_ATTRIBUTE? "=~" ENTITY_ATTRIBUTE_VALUE  // 实体属性值正则匹配

    ENTITY_TYPE: /[\u4e00-\u9fff\w]+|'([^']*)'/              // 匹配中文汉字和英文标识符， 兼容单引号包裹的情况
    ENTITY_ATTRIBUTE: "." /[\u4e00-\u9fff\w]+|'([^']*)'/     // 匹配中文汉字和英文标识符,属性必须以'.'开头， 兼容单引号包裹的情况
    ENTITY_ATTRIBUTE_VALUE: /[\u4e00-\u9fff\w]+|'([^']*)'/   // 匹配中文汉字和英文标识符， 兼容单引号包裹的情况

    %import common.WS_INLINE
    %ignore WS_INLINE
    """
    

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
   

rule_engine = Lark(grammar, parser="lalr", transformer=Neo4jCyberSyntaxTree()).parse

def evaluate_rule(rules:str|list[str]):
    batch_result = {}
    if isinstance(rules,str):
        rules = [rules]
    with driver.session() as session:
        for rule in rules:
            # 执行引擎，返回 neo4j 查询语句
            cyper_query = rule_engine(rule)
            
            #执行 cyber_query ，从数据库中返回结果
            result = list(session.run(cyper_query))
            
            # 确保每行每列都返回真 才算通过
            is_pass = all([all(record.values()) for record in result])
            
            log.info(f"run rule:【{rule}】,{"PASS" if is_pass else "NO_PASS"}")
            batch_result[rule] = is_pass
            
    return batch_result

def evaluate_rule_file(file_path:str):
    path = Path(file_path)
    if not path.exists():
        log.error(f"{file_path} do not exists!")
        return
    
    rule_files = []
    if path.is_file():
        rule_files = [file_path]
    elif path.is_dir():
        rule_files = glob.glob(f"{file_path}/**/*.yaml", recursive=True)
        rule_files += glob.glob(f"{file_path}/**/*.yml", recursive=True)
    
    for rule_file in rule_files:
        log.info(f"正则扫描策略文件:{rule_file}")
        try:
            with open(rule_file, 'r') as file:
                data = yaml.safe_load(file)
                if not data.get('rules'):
                    log.error(f"{rule_file} 中不存在 rules 节点")
                    continue
                rules = data['rules']
                result = evaluate_rule(rules)
                log.info(f"策略：{rule_file} 执行完成，成功:{sum(result.values())}条，失败:{len(result)-sum(result.values())}条，成功率:{sum(result.values())/len(result):.2%}。")
        except Exception as ex:
            log.error(f"execute {rule_file} failed,",ex)
                

if __name__ == "__main__":
    
    if len(sys.argv) > 1:
        rule_file = sys.argv[1]
        evaluate_rule_file(rule_file)

    # evaluate_rule(["症状.描述=发烧"])
    # evaluate_rule("疾病=胃肠炎")
    # evaluate_rule("not 症状.描述=发烧")
    # evaluate_rule("'症状'='流鼻涕' and '疾病'='肠胃炎' and ('药品'='阿托品' or '药品'='芬必得')")
    # evaluate_rule("'症状'='流鼻涕,发烧'")