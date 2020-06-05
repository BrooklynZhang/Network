import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket
from flow import BaseFlow
from collections import defaultdict

class UE(object):

    def __init__(self, env, ue_id):
        self.env = env
        self.ue_id = ue_id
        self.adj_ports = {}
        self.env.process(self.start_radar_routing())
        self.flows = {}
        self.timetable = defaultdict(int)
        self.data_packet_time = {}

    def start_radar_routing(self):
        print("UE",self.ue_id ,"Start Radar Routing at", self.env.now)
        tag = 0
        while True:
            self.send_to_all_expect(RadarPacket(self.ue_id, tag))
            yield self.env.timeout(5)
            tag += 1

    def get_host_id(self):
        return self.ue_id

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception('Duplicate port name')
        self.adj_ports[source_id] = source_port

    def send_to_dest(self, packet, dest_id):
        next_jump_port = self.timetable[dest_id][0]
        self.send(next_jump_port, packet)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.ue_id)

    def receive(self, packet, source_id):
        if packet.head == 'r':
            print('UE', self.ue_id, 'receives the data packet from', packet.src_host_id, 'at', self.env.now)
            self.send(source_id, EchoPacket(packet.src_host_id, self.ue_id, packet.tag))

        elif packet.head == 'e':
            print('UE', self.ue_id, 'receivess the Echo packet from', packet.src_host_id, 'at', self.env.now)
            packet.add_path(self.ue_id)
            tag = packet.tag
            origin_id = packet.src_host_id
            if self.timetable[origin_id] == 0:
                self.timetable[origin_id] = (source_id, tag)
            else:
                if tag > self.timetable[origin_id][1]:
                    self.timetable[origin_id] = (source_id, tag)
            print('UE: The Path of Echo packet is', packet.path)


        elif packet.head == 'd':
            self.send(source_id, AckPacket(packet.dest_host_id, packet.src_host_id, packet.flow_id, packet.packet_no,
                                           self.env.now))

        elif packet.head == 'a':
            key = (packet.packet_no, packet.flow_id)
            senttime = self.data_packet_time[key]
            print('UE', self.ue_id, 'receive the ack packet from', packet.src_host_id,'response time is', self.env.now - senttime)


    def add_flow(self, flow):
        print('adding flow to UE', self.ue_id,'at',self.env.now)
        self.flows[flow.flow_id] = flow
        self.env.process(self.send_data_packets(flow))

    def send_data_packets(self, flow):
        yield self.env.timeout(flow.start_s)
        while flow.num_packets >= 0:
                print('UE',self.ue_id,"Send DataPacket", flow.num_packets,'to',flow.dest_id)
                datapacket_id = flow.num_packets
                packet = DataPacket(flow.src_id, flow.dest_id, flow.flow_id, datapacket_id, self.env.now) #src_host_id, dest_host_id, flow_id, packetnum, timestamp
                key = (datapacket_id, flow.flow_id)
                self.data_packet_time[key] = self.env.now
                self.send_to_dest(packet, flow.dest_id)
                flow.num_packets -= 1
