from graphrag import es_graph_update


def t1():
    tenant_id = '111'
    kb_id = '111'
    doc_id = '111'
    node_name = "abc"
    description = 'abc_desc'
    attrs = {'doc_id': doc_id, 'description': description,
             'rank': 1, 'weight': 1}
    es_graph_update.upsert_node(tenant_id, kb_id, node_name, attrs)
