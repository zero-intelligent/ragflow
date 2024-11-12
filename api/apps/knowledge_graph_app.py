from collections import defaultdict
from functools import reduce
from flask import request
from api.utils.api_utils import get_json_result, validate_request
from graphrag.es_graph_update import upsert_nodes,delete_nodes,upsert_links,delete_links
from loguru import logger as log


@manager.route('/trigger', methods=['POST'])
@validate_request("tenant_id","kb_id")
def trigger(tenant_id:str = "", kb_id:str = ""):
    req = request.json
    log.debug(req)
    
    if createdNodes := req.get('createdNodes'):
        upsert_nodes(tenant_id,kb_id,createdNodes)
    
    if deletedNodes := req.get('deletedNodes'):
        node_ids = [n['id'] for n in deletedNodes]
        delete_nodes(tenant_id,kb_id,node_ids)
        
    if createdRelationships := req.get('createdRelationships'):
        upsert_links(tenant_id,kb_id,createdRelationships)
    
    if deletedRelationships := req.get('deletedRelationships'):
        relation_ids = [r['id'] for r in deletedRelationships]
        delete_links(tenant_id,kb_id,relation_ids)
        
    if assignedNodeProperties := req['assignedNodeProperties']:
        def merge(acc,item):
            id = item['node']['id']
            acc[id] |= item['node']['properties']
            return acc
        update_nodes_dict = reduce(merge,assignedNodeProperties, defaultdict(dict))
        upsert_nodes(tenant_id,kb_id,update_nodes_dict)
    
    if assignedRelationshipProperties := req['assignedRelationshipProperties']:
        def merge(acc,item):
            id = item['relationship']['id']
            acc[id] |= item['relationship']['properties']
            return acc
        update_relations_dict = reduce(merge,assignedRelationshipProperties, defaultdict(dict))
        upsert_links(tenant_id,kb_id,update_relations_dict)
        
    return get_json_result(data=True)


