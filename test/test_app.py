import unittest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['DB_BACKEND'] = 'sqlite'
os.environ['SQLITE_DB'] = ':memory:'

from app import app, init_db

class TestAPI(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        with app.app_context():
            init_db()

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('timestamp', data)

    def test_post_metrics_valid(self):
        payload = [
            {'hostname': 'test-host', 'metric': 'cpu', 'value': 45.2, 'unit': '%'},
            {'hostname': 'test-host', 'metric': 'memory', 'value': 67.1, 'unit': '%'}
        ]
        response = self.client.post(
            '/metrics',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['stored'], 2)

    def test_post_metrics_empty_body(self):
        response = self.client.post(
            '/metrics',
            data='',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_post_metrics_not_list(self):
        payload = {'hostname': 'test', 'metric': 'cpu', 'value': 45.2, 'unit': '%'}
        response = self.client.post(
            '/metrics',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_post_metrics_invalid_metric_name(self):
        payload = [{'hostname': 'test', 'metric': 'invalid_metric', 'value': 45.2, 'unit': '%'}]
        response = self.client.post(
            '/metrics',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['stored'], 0)

    def test_get_metrics_empty(self):
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('count', data)
        self.assertIn('measurements', data)

    def test_get_metrics_after_post(self):
        payload = [{'hostname': 'test-host', 'metric': 'cpu', 'value': 55.0, 'unit': '%'}]
        self.client.post('/metrics', data=json.dumps(payload), content_type='application/json')
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertGreater(data['count'], 0)

if __name__ == '__main__':
    unittest.main()
