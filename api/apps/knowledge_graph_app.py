from itertools import chain
from flask import request
from api.settings import RetCode
from api.utils.api_utils import get_json_result
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService
from graphrag.es_graph_update import add_links, create_nodes, update_links, update_nodes,delete_nodes,delete_links
from loguru import logger as log


@manager.route('/trigger', methods=['POST'])
def trigger():
    """
        用来订阅 neo4j 的修改信息传递到 api 服务，相关neo4j 的修改逻辑见：graphrag/db/update.py ,例如：
        :use system;
        CALL apoc.trigger.install(
            'neo4j',
            'sendAllChangesToApi',
            "CALL apoc.load.jsonParams(
                'http://8.140.49.13:9381/v1/knowledge_graph/trigger?tenant_id=7d19a176807611efb0f80242ac120006&kb_id=fb7c4312973b11ef88ed0242ac120006',  // 外部 API 的 URL
                {method: 'POST'},  // 使用 POST 方法
                apoc.convert.toJson({
                    createdNodes: $createdNodes,
                    deletedNodes: $deletedNodes,
                    createdRelationships: $createdRelationships,
                    deletedRelationships: $deletedRelationships,
                    assignedNodeProperties: $assignedNodeProperties,
                    assignedRelationshipProperties: $assignedRelationshipProperties
                })
            ) YIELD value
            RETURN value",
            {phase: 'before'}
        )
    
        测试脚本如下：
        curl -X POST "http://8.140.49.13:9381/v1/knowledge_graph/trigger?tenant_id=7d19a176807611efb0f80242ac120006&kb_id=fb7c4312973b11ef88ed0242ac120006" -H 'Content-Type: application/json' -d'
        {
            "createdNodes": [],
            "deletedNodes": [],
            "createdRelationships": [],
            "deletedRelationships": [],
            "assignedNodeProperties": [],
            "assignedRelationshipProperties": []
        }
        '
        实际测试过程中，需要补充具体的修改信息，不能全是空值
    """
    log.debug(f"args:{request.args},payload:{request.json}")
    
    tenant_id = request.args.get('tenant_id')
    kb_id = request.args.get('kb_id')
    
    if not (tenant := TenantService.get_or_none(id=tenant_id)):
        return get_json_result(data=False, retmsg=f'tenant:{tenant_id} invalid or not exists.',retcode=RetCode.ARGUMENT_ERROR)
    
    if not (kb := KnowledgebaseService.get_or_none(id=kb_id)):
        return get_json_result(data=False, retmsg=f'kb_id:{kb_id} invalid or not exists.',retcode=RetCode.ARGUMENT_ERROR)

    req = request.json    
    if createdNodes := req.get('createdNodes'):
        create_nodes(tenant,kb,createdNodes)
    
    if deletedNodes := req.get('deletedNodes'):
        delete_nodes(tenant,kb,deletedNodes)
        
    if createdRelationships := req.get('createdRelationships'):
        add_links(tenant,kb,createdRelationships)
    
    if deletedRelationships := req.get('deletedRelationships'):
        delete_links(tenant,kb,deletedRelationships)
        
    if assignedNodeProperties := req.get('assignedNodeProperties'):
        create_node_ids = [n['id'] for n in createdNodes]
        # 获取所有nodes
        nodes = [n['node'] for n in chain(*assignedNodeProperties.values()) if n['node']['id'] not in create_node_ids]
        if nodes:
            # 按照id去重
            nodes = list({n['id']:n for n in nodes}.values())
            update_nodes(tenant,kb,nodes)
    
    if assignedRelationshipProperties := req.get('assignedRelationshipProperties'):
        create_link_ids = [r['id'] for r in createdRelationships]
        # 获取所有 links 
        links = [n['relationship'] for n in chain(*assignedRelationshipProperties.values()) if n['relationship']['id'] not in create_link_ids]
        if links:
            # 按照id去重
            links = list({n['id']:n for n in links}.values())
            update_links(tenant,kb,links)
        
    return get_json_result(data=True)

