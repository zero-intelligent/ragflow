
from neo4j import GraphDatabase

 # 连接到 Neo4j 数据库
uri = "bolt://localhost:7687"  # Neo4j 的 URI
username = "neo4j"               # 用户名
password = "bitzero123"       # 密码

driver = GraphDatabase.driver(uri, auth=(username, password))

def query(query:str):
    with driver.session() as session:
        return list(session.run(query))
            
