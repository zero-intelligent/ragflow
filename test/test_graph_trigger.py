

import pytest
from api.apps import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_home(client):
    response = client.get('/')
    assert response.status_code == 200

def test_update_node_properties(client):
    # 定义查询参数
    query_params = {
        'tenant_id': '7d19a176807611efb0f80242ac120006',
        'kb_id': 'fb7c4312973b11ef88ed0242ac120006'
    }
    
    # 修改节点多个属性
    data = {
        'deletedNodes': [],
        'deletedRelationships': [],
        'assignedRelationshipProperties': {},
        'createdRelationships': [],
        'assignedNodeProperties': {
            'description': [{
                'node': {
                    'id': '6',
                    'type': 'node',
                    'labels': ['RESTRAINT-METHOD(保定法)'],
                    'properties': {
                        'entity_type': 'RESTRAINT-METHOD (保定法)',
                        'weight': 2,
                        'description': 'description: 为防止人被咬伤而对犬使用的保定方法之一，包括使用市场上销售的各种材料制成的口套或用绷带/细绳扎住嘴部。5',
                        'rank': 1,
                        'source_id': '094小动物疾病学.pdf.txt-0',
                        'id': 'MUZZLE-RESTRAINT (口套和扎口保定法)'
                    }
                },
                'new': 'description: 为防止人被咬伤而对犬使用的保定方法之一，包括使用市场上销售的各种材料制成的口套或用绷带/细绳扎住嘴部。5',
                'old': 'description: 为防止人被咬伤而对犬使用的保定方法之一，包括使用市场上销售的各种材料制成的口套或用绷带/细绳扎住嘴部。4',
                'key': 'description'
            }],
            'weight': [{
                'node': {
                    'id': '6',
                    'type': 'node',
                    'labels': ['RESTRAINT-METHOD(保定法)'],
                    'properties': {
                        'entity_type': 'RESTRAINT-METHOD (保定法)',
                        'weight': 2,
                        'description': 'description: 为防止人被咬伤而对犬使用的保定方法之一，包括使用市场上销售的各种材料制成的口套或用绷带/细绳扎住嘴部。5',
                        'rank': 1,
                        'source_id': '094小动物疾病学.pdf.txt-0',
                        'id': 'MUZZLE-RESTRAINT (口套和扎口保定法)'
                    }
                },
                'new': 2,
                'old': 1,
                'key': 'weight'
            }]
        },
        'createdNodes': []
    }
    
    # 发送 POST 请求
    response = client.post('/v1/knowledge_graph/trigger', 
                           json=data, 
                           query_string=query_params,
                           headers={
        'Content-Type': 'application/json'
    })
    
    # 检查响应状态码
    assert response.status_code == 200
    
    # 检查响应数据
    response_data = response.get_json()
    
   
    assert response_data['data']
    

def test_update_relation_properties(client):
    # 定义查询参数
    query_params = {
        'tenant_id': '7d19a176807611efb0f80242ac120006',
        'kb_id': 'fb7c4312973b11ef88ed0242ac120006'
    }
   
    # 修改边多个属性
    data = {
        'deletedNodes': [],
        'deletedRelationships': [],
        'assignedRelationshipProperties': {
            'descripion': [{
                'new': '金毛寻猎犬易发髋关节发育异常，这是一种常见的遗传性疾病。2',
                'old': None,
                'relationship': {
                    'id': '202',
                    'type': 'relationship',
                    'label': 'CONNECTED_TO',
                    'start': {
                        'id': '117515',
                        'type': 'node',
                        'labels': ['BREED(品种)'],
                        'properties': {
                            'entity_type': 'BREED(品种)',
                            'weight': 1,
                            'rank': 0,
                            'description': '金毛寻猎犬也是脊髓肿瘤的高发品种。',
                            'source_id': '/home/admin/python_projects/MedicalGPT/data/pretrain/pet_books/宠医临床书籍/【61】小动物临床手册.pdf.txt-graph_25000',
                            'id': 'GOLDEN-RETRIEVER(金毛寻猎犬)'
                        }
                    },
                    'end': {
                        'id': '239089',
                        'type': 'node',
                        'labels': ['DISEASE(疾病)'],
                        'properties': {
                            'entity_type': 'DISEASE(疾病)',
                            'rank': 2,
                            'weight': 2,
                            'description': '一种常见的犬类遗传性疾病，影响髋关节的正常发育，导致关节不稳定和疼痛。犬髋关节发育异常，可能导致后肢步态不稳。',
                            'source_id': '14训犬相关/狗狗成长日志++驯养与疾病防治.pdf.txt-graph_1000',
                            'id': 'HIP-JOINT-DYSPLASIA(髋关节发育异常)'
                        }
                    },
                    'properties': {
                        'descripion': '金毛寻猎犬易发髋关节发育异常，这是一种常见的遗传性疾病。2',
                        'weight': 2,
                        'description': '金毛寻猎犬易发髋关节发育异常，这是一种常见的遗传性疾病。',
                        'source_id': '14训犬相关/狗狗成长日志++驯养与疾病防治.pdf.txt-graph_1000'
                    }
                },
                'key': 'descripion'
            }],
            'weight': [{
                'new': 2,
                'old': '1.0',
                'relationship': {
                    'id': '202',
                    'type': 'relationship',
                    'label': 'CONNECTED_TO',
                    'start': {
                        'id': '117515',
                        'type': 'node',
                        'labels': ['BREED(品种)'],
                        'properties': {
                            'entity_type': 'BREED(品种)',
                            'weight': 1,
                            'rank': 0,
                            'description': '金毛寻猎犬也是脊髓肿瘤的高发品种。',
                            'source_id': '/home/admin/python_projects/MedicalGPT/data/pretrain/pet_books/宠医临床书籍/【61】小动物临床手册.pdf.txt-graph_25000',
                            'id': 'GOLDEN-RETRIEVER(金毛寻猎犬)'
                        }
                    },
                    'end': {
                        'id': '239089',
                        'type': 'node',
                        'labels': ['DISEASE(疾病)'],
                        'properties': {
                            'entity_type': 'DISEASE(疾病)',
                            'rank': 2,
                            'weight': 2,
                            'description': '一种常见的犬类遗传性疾病，影响髋关节的正常发育，导致关节不稳定和疼痛。犬髋关节发育异常，可能导致后肢步态不稳。',
                            'source_id': '14训犬相关/狗狗成长日志++驯养与疾病防治.pdf.txt-graph_1000',
                            'id': 'HIP-JOINT-DYSPLASIA(髋关节发育异常)'
                        }
                    },
                    'properties': {
                        'descripion': '金毛寻猎犬易发髋关节发育异常，这是一种常见的遗传性疾病。2',
                        'weight': 2,
                        'description': '金毛寻猎犬易发髋关节发育异常，这是一种常见的遗传性疾病。',
                        'source_id': '14训犬相关/狗狗成长日志++驯养与疾病防治.pdf.txt-graph_1000'
                    }
                },
                'key': 'weight'
            }]
        },
        'createdRelationships': [],
        'assignedNodeProperties': {},
        'createdNodes': []
    }
    # 发送 POST 请求
    response = client.post('/v1/knowledge_graph/trigger', 
                           json=data, 
                           query_string=query_params,
                           headers={
        'Content-Type': 'application/json'
    })
    
    # 检查响应状态码
    assert response.status_code == 200
    
    # 检查响应数据
    response_data = response.get_json()
    
   
    assert response_data['data']
    
    