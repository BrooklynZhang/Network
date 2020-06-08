import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket

import numpy as np

class IAB_Node(object):

    def __init__(self, env, node_id, algorithm):

        self.env = env
        self.node_id = node_id
        self.adj_ports = {}
        self.algorithm = algorithm

        if self.algorithm == 'dijkstra':
            self.radar_tag_table = {}
            self.backwardspacket = {}
            self.forwardspaceket = {}

        if self.algorithm == 'q':
            self.time_stamp_table = {}
            self.q_routing_table = {}
            self.q_routing_back_table = {}
            self.discount_factor = 0.9
            self.learning_rate = 0.1
            self.epsilon = 0.1

    def initialize(self):
        if self.algorithm == 'q':
            for port in self.adj_ports:
                self.q_routing_table[port] = 0

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception("ERROR: Duplicate port name")
        self.adj_ports[source_id] = source_port

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.node_id)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def receive(self, packet, source_id):
        if packet.head == 'r':
            if self.algorithm == 'dijkstra' or self.algorithm == 'q':
                src_host_id = packet.src_host_id
                router_tag_table = self.radar_tag_table
                tag = packet.tag
                if src_host_id not in router_tag_table or router_tag_table[
                    src_host_id] < tag:  ## the radar message come here first time or need to update the information
                    router_tag_table[src_host_id] = tag
                    self.backwardspacket[src_host_id] = source_id
                    self.send_to_all_expect(packet, source_id)

        elif packet.head == 'e':
            if self.algorithm == 'dijkstra' or self.algorithm == 'q':
                dest_host_id = packet.dest_host_id
                router_tag_table = self.radar_tag_table
                tag = packet.tag
                if dest_host_id in router_tag_table and router_tag_table[dest_host_id] == tag:
                    self.forwardspaceket[packet.src_host_id] = source_id
                    packet.add_path(self.node_id)
                    self.send(self.backwardspacket[dest_host_id], packet)

        elif packet.head == 'd':
            if self.algorithm == 'dijkstra':
                self.send(self.search_next_jump_forward(packet.dest_host_id), packet)
            elif self.algorithm == 'q':
                action = self.get_action()
                key = (packet.packet_no, packet.flow_id)
                self.q_routing_back_table[key] = source_id
                self.time_stamp_table[key] = self.env.now
                self.send(action, packet)

        elif packet.head == 'a':
            if self.algorithm == 'dijkstra':
                self.send(self.search_next_jump_backward(packet.dest_host_id), packet)
            elif self.algorithm == 'q':
                self.updating_q_routing_table(packet, source_id)
                key = (packet.packet_no, packet.flow_id)
                self.send(self.q_routing_back_table[key], packet)

    def get_action(self):
        if np.random.rand() < self.epsilon:
            action = np.random.choice(list(self.q_routing_table.keys()))
        else:
            action = max(self.q_routing_table, key = self.q_routing_table.get)
        return action

    def updating_q_routing_table(self, packet, source_id):
        reward = self.calculate_reward(packet)
        current_q = self.q_routing_table[source_id]
        max_q = max(self.q_routing_table, key = self.q_routing_table.get)
        new_q = reward + self.discount_factor * self.q_routing_table[max_q]
        self.q_routing_table[source_id] += self.learning_rate * (new_q - current_q)

    def calculate_reward(self, packet):
        future_reward = packet.reward
        key = (packet.packet_no, packet.flow_id)
        delay = self.env.now - self.time_stamp_table[key] #The shorter the delay, the larger the reward example 0.11383424000000031
        reward = future_reward - (100 * delay)
        return reward

    def search_next_jump_forward(self, dest_id):
        if dest_id in self.forwardspaceket:
            return self.forwardspaceket[dest_id]
        else:
            raise Exception("ERROR: Can not find forwarding path", self.node_id)
            return None

    def search_next_jump_backward(self, dest_id):
        if dest_id in self.backwardspacket:
            return self.backwardspacket[dest_id]
        else:
            raise Exception("ERROR: Can not find forwarding path", self.node_id)
            return None

