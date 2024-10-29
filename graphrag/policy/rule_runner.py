import sys
import yaml
import glob
from pathlib import Path
from loguru import logger as log
from graphrag.policy.graph_transformer import evaluate_rule_on_network_graph
from graphrag.policy.neo4jquery_transformer import evaluate_rule_on_neo4j

def evaluate_rule_file(file_path:str):
    '''
        将 file_path 下的所有 yaml 格式的规则文件扫描，逐个执行配置规则，直到全部完成
    '''
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
                if data.get('disable'):
                    continue
                name = data['name']
                source = data.get('source','global')
                if not data.get('rules'):
                    log.error(f"{rule_file} 中不存在 rules 节点")
                    continue
                rules = data['rules']
                
                log.info(f"{rule_file},evaluating rule:{name},source:{source},{len(rules)} rules")
                if source == 'global':
                    result = evaluate_rule_on_neo4j(rules)
                else:
                    result = evaluate_rule_on_network_graph(rules,doc=source)
                log.info(f"策略：{rule_file} 执行完成，成功:{sum(result.values())}条，失败:{len(result)-sum(result.values())}条，成功率:{sum(result.values())/len(result):.2%}。")
        except Exception as ex:
            log.error(f"execute {rule_file} failed,{str(ex)}",exc_info=True)
                

if __name__ == "__main__":
    
    rule_file = "/home/admin/python_projects/ragflow/graphrag/policy/rules"
    if len(sys.argv) > 1:
        rule_file = sys.argv[1]
    # evaluate_rule_file(rule_file)
    evaluate_rule_file(rule_file)
