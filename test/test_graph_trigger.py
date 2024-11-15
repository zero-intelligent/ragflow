

import pytest
from api.apps import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_home(client):
    response = client.get('/')
    assert response.status_code == 200

def test_api_data(client):
    # 定义查询参数
    query_params = {
        'tenant_id': '7d19a176807611efb0f80242ac120006',
        'kb_id': 'fb7c4312973b11ef88ed0242ac120006'
    }
    # 定义请求体数据
    data =  {
            "createdNodes": [],
            "deletedNodes": [],
            "createdRelationships": [],
            "deletedRelationships": [],
            "assignedNodeProperties": [],
            "assignedRelationshipProperties": []
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
    
