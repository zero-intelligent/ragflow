
from neo4j import GraphDatabase
from rag.settings import NEO4J

driver = GraphDatabase.driver(uri=NEO4J['uri'], auth=(NEO4J['username'], NEO4J['password']))

def query(query:str):
    with driver.session() as session:
        return session.run(query)
            