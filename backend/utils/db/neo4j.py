# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      neo4j
   Description:
   Author:          Lijiamin
   date：           2023/7/19 09:56
-------------------------------------------------
   Change Activity:
                    2023/7/19 09:56
-------------------------------------------------
"""
from py2neo import Graph, Node, Relationship
from confload.confload import config

# # 创建节点
# router1 = Node("Router", name="Router1")
# router2 = Node("Router", name="Router2")
#
# # 创建关系
# connected_to = Relationship(router1, "CONNECTED_TO", router2, distance=10)
#
# # 将节点和关系添加到图数据库
# graph.create(router1)
# graph.create(router2)
# graph.create(connected_to)



class Neo4J:
    def __init__(self, DEVICE_LABEL='Router', CONNECTION_RELATIONSHIP='CONNECTED_TO', VRF_LABEL='VRF'):
        # 连接到Neo4j数据库
        self.graph = Graph(config.neo4j, auth=("neo4j", "01234567AA"))
        # 定义节点和关系标签
        self.DEVICE_LABEL = DEVICE_LABEL
        self.CONNECTION_RELATIONSHIP = CONNECTION_RELATIONSHIP
        self.VRF_LABEL = VRF_LABEL
        self.UNDERLAY_ROUTE_LABEL = "Underlay"
        self.OVERLAY_ROUTE_LABEL = "Overlay"

    # 创建节点
    def create_device(self, name, ip):
        device = Node(self.DEVICE_LABEL, name=name, ip=ip)
        self.graph.merge(device, self.DEVICE_LABEL, "name")
        return device

    # 创建关系
    def create_connection(self, device1, device2):
        connection = Relationship(device1, self.CONNECTION_RELATIONSHIP, device2)
        self.graph.merge(connection)

    # 创建VRF节点
    def create_vrf(self, name):
        vrf = Node(self.VRF_LABEL, name=name)
        self.graph.merge(vrf, self.VRF_LABEL, "name")
        return vrf

    # 存储底层路由信息
    def store_underlay_routing_table(self, device_name, routing_table):
        device = self.graph.nodes.match(self.DEVICE_LABEL, name=device_name).first()
        for route in routing_table:
            properties = {
                "destination_ip": route["destination_ip"],
                "mask": route["mask"],
                "next_hop_ip": route["next_hop_ip"],
                "route_type": route["route_type"]
            }
            route_node = Node(self.UNDERLAY_ROUTE_LABEL, **properties)
            self.graph.merge(route_node, self.UNDERLAY_ROUTE_LABEL, "destination_ip", "mask", "next_hop_ip", "route_type")
            self.graph.merge(Relationship(device, "HAS_UNDERLAY_ROUTE", route_node))

    # 存储VRF路由信息
    def store_overlay_routing_table(self, device_name, vrf_name, routing_table):
        device = self.graph.nodes.match(self.DEVICE_LABEL, name=device_name).first()
        vrf = self.create_vrf(vrf_name)
        self.graph.merge(Relationship(device, "HAS_VRF", vrf))
        for route in routing_table:
            properties = {
                "destination_ip": route["destination_ip"],
                "mask": route["mask"],
                "next_hop_ip": route["next_hop_ip"],
                "route_type": route["route_type"]
            }
            route_node = Node(self.OVERLAY_ROUTE_LABEL, **properties)
            self.graph.merge(route_node, self.OVERLAY_ROUTE_LABEL, "destination_ip", "mask", "next_hop_ip", "route_type")
            self.graph.create(Relationship(vrf, "HAS_OVERLAY_ROUTE", route_node))

    # 查询指定节点是否具有到某一个网段的路由，并给出路由路径信息
    def query_route_path(self, device_name, destination_ip):
        """
        MATCH (start:Device {name: 'Device1'}), (end:Device {name: 'Device2'})
        CALL algo.shortestPath.stream(start, end, 'CONNECTED_TO')
        YIELD nodeId, cost
        RETURN algo.getNodeById(nodeId).name AS deviceName, cost
        """
        query = f"""
        MATCH (device:{self.DEVICE_LABEL} {{name: $device_name}})
        MATCH path = (device)-[:HAS_UNDERLAY_ROUTE]->(route:{self.UNDERLAY_ROUTE_LABEL} {{destination_ip: $destination_ip}})
        RETURN path
        """
        result = self.graph.run(query, device_name=device_name, destination_ip=destination_ip)
        return result

# 查询数据
# result = graph.run("MATCH (r:Router) RETURN r.name AS name")
# for record in result:
#     print(record['name'])

# 关闭连接
# graph.close()


