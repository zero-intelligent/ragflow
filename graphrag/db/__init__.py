
from neo4j import GraphDatabase
from rag.settings import NEO4J
from loguru import logger as log

driver = GraphDatabase.driver(uri=NEO4J['uri'], auth=(NEO4J['username'], NEO4J['password']))

def query(query:str):
    with driver.session() as session:
        return session.run(query)
            
def execute_update(cql:str):
    try:
        with driver.session() as session:
            results = session.run(cql)
            counters = results.consume().counters
            counter_attrs = {attr: getattr(counters, attr) for attr in dir(counters)}
            counter_repr = [f"{v} {k}" for k,v in counter_attrs.items() if v and type(v) is int]
            if counters.contains_updates:
                log.info(','.join(counter_repr))
            else:
                log.info('no update.')
    except Exception as ex:
        log.error(f"{str(ex)}")
        