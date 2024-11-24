from concurrent.futures import ThreadPoolExecutor
from itertools import chain
from flask import request
from api.settings import RetCode
from api.utils.api_utils import get_json_result
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService
from graphrag.es_graph_update import add_links, create_nodes, update_links, update_nodes,delete_nodes,delete_links
from loguru import logger as log


executor = ThreadPoolExecutor(max_workers=32)


def call_func(func,*args):
    if request.args.get('sync'):
        func(*args)
    else:
        executor.submit(func,*args)
    
@manager.route('/trigger', methods=['POST'])
def trigger():
    """
        用来订阅 neo4j 的修改信息传递到 api 服务，相关neo4j 的修改逻辑见：graphrag/db/update.py ,例如：
        :use system;
        CALL apoc.trigger.install(
            'neo4j',
            'sendAllChangesToApi',
            "CALL apoc.load.jsonParams(
                'http://39.101.69.172:9381/v1/knowledge_graph/trigger?tenant_id=7d19a176807611efb0f80242ac120006&kb_id=fb7c4312973b11ef88ed0242ac120006',  // 外部 API 的 URL
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
        curl -X POST "http://39.101.69.172:9381/v1/knowledge_graph/trigger?tenant_id=7d19a176807611efb0f80242ac120006&kb_id=fb7c4312973b11ef88ed0242ac120006" -H 'Content-Type: application/json' -d'
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
    log.debug(f"trigger args:{request.args},payload:{request.json}")
    
    tenant_id = request.args.get('tenant_id')
    kb_id = request.args.get('kb_id')
    
    if not (tenant := TenantService.get_or_none(id=tenant_id)):
        return get_json_result(data=False, retmsg=f'tenant:{tenant_id} invalid or not exists.',retcode=RetCode.ARGUMENT_ERROR)
    
    if not (kb := KnowledgebaseService.get_or_none(id=kb_id)):
        return get_json_result(data=False, retmsg=f'kb_id:{kb_id} invalid or not exists.',retcode=RetCode.ARGUMENT_ERROR)

    req = request.json    
    if createdNodes := req.get('createdNodes'):
        call_func(create_nodes,tenant,kb,createdNodes)
    
    if deletedNodes := req.get('deletedNodes'):
        call_func(delete_nodes,tenant,kb,deletedNodes)
        
    if createdRelationships := req.get('createdRelationships'):
        call_func(add_links,tenant,kb,createdRelationships)
    
    if deletedRelationships := req.get('deletedRelationships'):
        call_func(delete_links,tenant,kb,deletedRelationships)
        
    if assignedNodeProperties := req.get('assignedNodeProperties'):
        create_node_ids = [n['id'] for n in createdNodes]
        # 获取所有nodes
        nodes = [n['node'] for n in chain(*assignedNodeProperties.values()) if n['node']['id'] not in create_node_ids]
        if nodes:
            # 按照id去重
            nodes = list({n['id']:n for n in nodes}.values())
            call_func(update_nodes,tenant,kb,nodes)
    
    if assignedRelationshipProperties := req.get('assignedRelationshipProperties'):
        create_link_ids = [r['id'] for r in createdRelationships]
        # 获取所有 links 
        links = [n['relationship'] for n in chain(*assignedRelationshipProperties.values()) if n['relationship']['id'] not in create_link_ids]
        if links:
            # 按照id去重
            links = list({n['id']:n for n in links}.values())
            call_func(update_links,tenant,kb,links)
        
    return get_json_result(data=True)


@manager.route('/user_custom_modify', methods=['POST'])
def user_custom_modify():
    """
    数据示例：
    {
        "createdNodes": [{
            "labels": ["LIFESTYLE(生活习惯)"],
            "properties": {
                "entity_type": "LIFESTYLE (生活习惯)",
                "rank": 6,
                "description": "华法林钠禁用于妊娠期，因为可引起先天性畸形。",
                "weight": 1,
                "source_id": "01宠物疾病/【06】《Plumb's兽药手册（第5版）》.pdf.txt-50000",
                "id": "PREGNANCY (妊娠)"
            }
        }],
        "assignedNodeProperties": [{
            "labels": ["LIFESTYLE(生活习惯)"],
            "properties": {
                "entity_type": "LIFESTYLE (生活习惯)",
                "rank": 6,
                "description": "华法林钠禁用于妊娠期，因为可引起先天性畸形。2",
                "weight": 1,
                "source_id": "01宠物疾病/【06】《Plumb's兽药手册（第5版）》.pdf.txt-50000",
                "id": "PREGNANCY (妊娠)"
            }
        }],
        "deletedNodes": [{
            "labels": ["LIFESTYLE(生活习惯)"],
            "properties": {
                "entity_type": "LIFESTYLE (生活习惯)",
                "source_id": "01宠物疾病/【06】《Plumb's兽药手册（第5版）》.pdf.txt-50000",
                "id": "PREGNANCY (妊娠)"
            }
        }],
        "createdRelationships": [{
            "type": "CONNECTED_TO",
            "start_node_id": "PREGNANCY (妊娠)",
            "end_node_id": "PHENYLBUTAZONE (保泰松)",
            "properties": {
                "weight": "1.0",
                "description": "尽管保泰松没有直接的致畸作用，但在啮齿动物中进行的研究表明该药具有降低胎仔数、增加新生儿死亡率和死胎率的不良作用。",
                "source_id": "01宠物疾病/【06】《Plumb's兽药手册（第5版）》.pdf.txt-80000"
            }
        }],
        "assignedRelationshipProperties": [{
            "type": "CONNECTED_TO",
            "start_node_id": "PREGNANCY (妊娠)",
            "end_node_id": "PHENYLBUTAZONE (保泰松)",
            "properties": {
                "weight": "1.0",
                "description": "尽管保泰松没有直接的致畸作用，但在啮齿动物中进行的研究表明该药具有降低胎仔数、增加新生儿死亡率和死胎率的不良作用。2",
                "source_id": "01宠物疾病/【06】《Plumb's兽药手册（第5版）》.pdf.txt-80000"
            }
        }],
        "deletedRelationships": [{
            "type": "CONNECTED_TO",
            "start_node_id": "PREGNANCY (妊娠)",
            "end_node_id": "PHENYLBUTAZONE (保泰松)",
            "properties": {
                "source_id": "01宠物疾病/【06】《Plumb's兽药手册（第5版）》.pdf.txt-80000"
            }
        }]
    }

    
    """
    log.debug(f"user_custom_modify args:{request.args},payload:{request.json}")
    
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
        update_nodes(tenant,kb,assignedNodeProperties)
    
    if assignedRelationshipProperties := req.get('assignedRelationshipProperties'):
        update_links(tenant,kb,assignedRelationshipProperties)
            
    return get_json_result(data=True)