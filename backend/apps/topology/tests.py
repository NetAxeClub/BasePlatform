from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from .models import Topology


class TopologyModelTest(TestCase):
    def test_create_topology(self):
        topology = Topology.objects.create(name="测试拓扑", memo="测试描述")
        self.assertEqual(topology.name, "测试拓扑")
        self.assertEqual(str(topology), "测试拓扑")

    def test_unique_name(self):
        Topology.objects.create(name="拓扑1")
        with self.assertRaises(Exception):
            Topology.objects.create(name="拓扑1")


class TopologyViewSetTest(APITestCase):
    def setUp(self):
        self.topology = Topology.objects.create(name="测试拓扑", memo="描述")

    def test_list_topologies(self):
        response = self.client.get('/api/topology/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_topology(self):
        data = {"name": "新拓扑", "memo": "新描述"}
        response = self.client.post('/api/topology/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TopologyShowTest(APITestCase):
    @patch('apps.topology.views.topology_mongo')
    def test_get_topology_success(self, mock_mongo):
        mock_mongo.find.return_value = [{"name": "test", "nodes": []}]
        response = self.client.get('/api/topology/show/?graph=test')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 200)

    @patch('apps.topology.views.topology_mongo')
    def test_get_topology_not_found(self, mock_mongo):
        mock_mongo.find.return_value = []
        response = self.client.get('/api/topology/show/?graph=notexist')
        self.assertEqual(response.json()['code'], 400)

    @patch('apps.topology.views.TopologyTask')
    def test_save_graph(self, mock_task):
        data = {"save_graph": {"name": "test", "nodes": []}}
        response = self.client.post('/api/topology/show/', data, format='json')
        self.assertEqual(response.json()['code'], 200)

    @patch('apps.topology.views.topology_mongo')
    def test_delete_topology(self, mock_mongo):
        response = self.client.delete('/api/topology/show/?graph=test')
        self.assertEqual(response.json()['code'], 200)


class IconViewTest(APITestCase):
    @patch('apps.topology.views.IconTree')
    def test_get_icons(self, mock_tree):
        mock_instance = MagicMock()
        mock_instance.tree_final = [{"name": "icon1"}]
        mock_tree.return_value = mock_instance
        response = self.client.get('/api/topology/icons/')
        self.assertEqual(response.json()['code'], 200)
