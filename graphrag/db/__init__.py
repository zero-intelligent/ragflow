
from neo4j import GraphDatabase
from rag.settings import NEO4J
from loguru import logger as log

driver = GraphDatabase.driver(uri=NEO4J['uri'], auth=(NEO4J['username'], NEO4J['password']))

def query(query:str):
    with driver.session() as session:
        return session.run(query)
            
def execute_update(cql:str):
    with driver.session() as session:
        results = session.run(cql)
        counters = results.consume().counters
        int_attributes = {attr: getattr(counters, attr) for attr in dir(counters)}
        count_repr = [f"{v} {k}" for k,v in int_attributes.items() if v and type(v) is int]
        if counters.contains_updates:
            log.info(','.join(count_repr))
        else:
            log.info('no update.')
        