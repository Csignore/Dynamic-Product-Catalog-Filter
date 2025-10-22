import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app


@pytest.fixture()
def app(tmp_path):
    db_uri = f"sqlite:///{tmp_path/'test.db'}"
    application = create_app(database_uri=db_uri)
    yield application
    with application.app_context():
        application.db.session.remove()
        application.db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _fetch_all_products(client, limit=100):
    items = []
    page = 1
    while True:
        res = client.get(f'/products?page={page}&limit={limit}')
        data = res.get_json()
        items.extend(data['items'])
        if len(items) >= data['total']:
            break
        page += 1
    return items


def test_happy_path_flow(client):
    res = client.post('/products/generate', json={'count': 120, 'seed': 42})
    assert res.status_code == 200
    assert res.get_json()['created'] == 120

    res = client.get('/products?limit=20&page=1')
    data = res.get_json()
    assert data['page'] == 1
    assert len(data['items']) == 20
    assert data['total'] == 120

    sample_brand = data['items'][0]['brand']
    res = client.get(f"/products/search?q={sample_brand[:3]}")
    sdata = res.get_json()
    assert sdata['total'] >= 1
    assert set(sdata['items'][0].keys()) == {
        'id', 'name', 'description', 'category', 'brand', 'price', 'stock', 'sku'
    }


def test_pagination_boundaries_and_validation(client):
    client.post('/products/generate', json={'count': 55})

    res = client.get('/products?limit=20&page=3')
    data = res.get_json()
    assert data['page'] == 3
    assert len(data['items']) == 15
    assert data['total'] == 55

    res = client.get('/products?limit=20&page=4')
    empty_page = res.get_json()
    assert empty_page['items'] == []
    assert empty_page['total'] == 55

    assert client.get('/products?page=0').status_code == 400
    assert client.get('/products?limit=0').status_code == 400


def test_input_validation_errors(client):
    assert client.post('/products/generate', json={'count': -5}).status_code == 400
    assert client.post('/products/generate', json={'count': 0}).status_code == 400
    assert client.post('/products/generate', json={'count': 2500}).status_code == 400
    assert client.post('/products/generate', json={'count': 'abc'}).status_code == 400

    assert client.get('/products?limit=500').status_code == 400
    resp = client.get('/products/search?q=')
    assert resp.status_code == 400
    assert resp.get_json()['error']


def test_multiple_generation_accumulates_and_keeps_unique_skus(client):
    client.post('/products/generate', json={'count': 30, 'seed': 1})
    client.post('/products/generate', json={'count': 40, 'seed': 2})

    items = _fetch_all_products(client, limit=50)
    assert len(items) == 70
    skus = [item['sku'] for item in items]
    assert len(set(skus)) == len(skus)


def test_persistence_across_app_instances(tmp_path):
    db_uri = f"sqlite:///{tmp_path/'persist.db'}"

    first = create_app(database_uri=db_uri)
    first_client = first.test_client()
    first_client.post('/products/generate', json={'count': 10, 'seed': 42})

    second = create_app(database_uri=db_uri)
    second_client = second.test_client()
    res = second_client.get('/products')
    assert res.status_code == 200
    assert res.get_json()['total'] == 10


def test_large_dataset_generation(client):
    response = client.post('/products/generate', json={'count': 1000})
    assert response.status_code == 200
    assert response.get_json()['created'] == 1000

    items = _fetch_all_products(client, limit=200)
    assert len(items) == 1000


def test_invalid_search_params(client):
    client.post('/products/generate', json={'count': 10})
    assert client.get('/products/search?q=Ac&page=0').status_code == 400
    assert client.get('/products/search?q=Ac&limit=0').status_code == 400
