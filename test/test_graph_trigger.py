

import inspect
import types
from api.apps import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_home(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Hello, World!' in response.data

def test_api_data(client):
    response = client.get('/api/data')
    assert response.status_code == 200
    data = response.get_json()
    assert data['key'] == 'value'