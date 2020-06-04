import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket

import simpy
from packet import RadarPacket, EchoPacket

class IAB_Node(object):

    def __init__(self, env, node_id):

        self.env = env
        self.node_id = node_id
        self.adj_ports = {}
        self.link_id_to_dest = {}
        self.radar_tag_table = {}
        self.backwardspacket = {}
        self.forwardspaceket = {}


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
            src_host_id = packet.src_host_id
            router_tag_table = self.radar_tag_table
            tag = packet.tag
            if src_host_id not in router_tag_table or router_tag_table[
                src_host_id] < tag:  ## the radar message come here first time or need to update the information
                router_tag_table[src_host_id] = tag
                self.backwardspacket[src_host_id] = source_id
                self.send_to_all_expect(packet, source_id)

        elif packet.head == 'e':
            src_host_id = packet.src_host_id
            router_tag_table = self.radar_tag_table
            tag = packet.tag
            if src_host_id in router_tag_table and router_tag_table[src_host_id] == tag:
                self.forwardspaceket[packet.dest_host_id] = source_id
                packet.add_path(self.node_id)
                self.send(self.backwardspacket[src_host_id], packet)

        elif packet.head == 'd':
            self.send(self.look_up(packet.dest_host_id), packet)

        elif packet.head == 'a':
            self.send(self.look_up(packet.dest_host_id), packet)

    def search_next_jump(self, dest_id):
        if dest_id in self.forwardspaceket:
            return self.forwardspaceket[dest_id]
        else:
            raise Exception("ERROR: Can not find forwarding path")
            return None