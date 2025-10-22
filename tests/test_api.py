import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app


def test_generate_and_search():
    app = create_app(testing=True)
    client = app.test_client()

    # initially empty
    res = client.get('/products')
    assert res.status_code == 200
    assert res.get_json()['total'] == 0

    # generate data
    res = client.post('/products/generate', json={'count': 120, 'seed': 42})
    assert res.status_code == 200
    assert res.get_json()['created'] == 120

    # list
    res = client.get('/products?limit=20&page=1')
    data = res.get_json()
    assert data['page'] == 1 and len(data['items']) == 20 and data['total'] == 120

    # search existing brand substring
    res = client.get('/products/search?q=Acme')
    sdata = res.get_json()
    assert sdata['total'] > 0

    # search empty query
    res = client.get('/products/search?q=')
    assert res.get_json()['total'] == 0
