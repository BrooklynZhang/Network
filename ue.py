import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket, HelloPacket, InformationPacket
from collections import defaultdict


class UE(object):

    def __init__(self, env, ue_id, algorithm):
        self.env = env
        self.ue_id = ue_id
        self.adj_ports = {}
        self.algorithm = algorithm
        self.flows = {}
        self.timetable = defaultdict(int)
        self.data_packet_time = {}
        self.monitor_data_act_time = {}
        self.env.process(self.get_access_to_iab())

        self.monitor_transmission_t = {}

        if self.algorithm == 'dijkstra':
            self.env.process(self.start_radar_routing())

    def add_flow(self, flow):
        self.flows[flow.flow_id] = flow
        self.env.process(self.send_data_packets(flow))

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception('ERROR: Duplicate port name')
        self.adj_ports[source_id] = source_port

    def get_access_to_iab(self):
        while True:
            packet = HelloPacket(self.ue_id)
            self.send_to_all_expect(packet)
            yield self.env.timeout(5)

    def receive(self, packet, source_id):
        '''if packet.head == 'r':
            print('UE', self.ue_id, 'receives the data packet from', packet.src_host_id, 'at', self.env.now)
            self.send(source_id, EchoPacket(packet.src_host_id, self.ue_id, packet.tag))'''

        if packet.head == 'e':
            #print('EVENT: UE', self.ue_id, 'receivess the Echo packet from', packet.src_host_id, 'at', self.env.now)
            packet.add_path(self.ue_id)
            tag = packet.tag
            origin_id = packet.src_host_id
            if self.timetable[origin_id] == 0:
                self.timetable[origin_id] = (source_id, tag)
                print('EVENT: UE', self.ue_id, 'received the Echo Packet. The path to IAB-DONOR is', packet.path)
            else:
                if tag > self.timetable[origin_id][1]:
                    self.timetable[origin_id] = (source_id, tag)
                    print('EVENT: UE Detected a quicker path. The new path to IAB-DONOR is', packet.path)

        #elif packet.head == 'd':
        #    self.send(source_id, AckPacket(packet.dest_host_id, packet.src_host_id, packet.src_node_id, packet.flow_id, packet.packet_no,
        #                                   self.env.now))
        elif packet.head == 'd':
            time_gap = self.env.now - packet.timestamp
            if packet.flow_id in self.monitor_transmission_t:
                self.monitor_transmission_t[packet.flow_id].append((packet.packet_no, time_gap))
            else:
                self.monitor_transmission_t[packet.flow_id] = [(packet.packet_no, time_gap)]
            if packet.ack == 'y':
                if self.algorithm in ['q', 'ant', 'dijkstra']:
                    if packet.packet_no % 500 == 0:
                        print('EVENT: IAB Donor', self.donor_id,'received the data packet from', packet.src_host_id, 'with packet id of', packet.packet_no, 'The uplink travel time is',time_gap)
                self.send(source_id, AckPacket(packet.dest_host_id, packet.src_host_id, packet.src_node_id, packet.flow_id, packet.packet_no, self.env.now, 'down'))
            else:
                if packet.packet_no % 500 == 0:
                    print('EVENT: UE', self.ue_id, 'received the data packet from', packet.src_host_id,
                          'with packet id of', packet.packet_no)


        elif packet.head == 'a':
            key = (packet.packet_no, packet.flow_id)
            senttime = self.data_packet_time[key]
            gap_time = self.env.now - senttime
            self.monitor_data_act_time[packet.flow_id].append((packet.packet_no, gap_time))
            if packet.packet_no % 500 == 0:
                print('EVENT: UE', self.ue_id, 'receive the ack packet', packet.packet_no,'response time is', gap_time)
        elif packet.head == 'r':
            if packet.src_host_id[0] == 'D':
                self.send(source_id, EchoPacket(self.ue_id, packet.src_host_id, packet.tag))


    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.ue_id)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def send_to_dest(self, packet, dest_id):
        if self.algorithm == 'dijkstra':
            next_jump_port = self.timetable[dest_id][0]
            self.send(next_jump_port, packet)
        elif self.algorithm in ['q', 'ant', 'dqn','genetic','pso']:
            self.send_to_all_expect(packet)

    def send_data_packets(self, flow):
        yield self.env.timeout(flow.start_s)
        print('EVENT: Adding flow to UE', self.ue_id, 'at', self.env.now)
        total_packets = flow.num_packets
        self.monitor_data_act_time[flow.flow_id] = []
        datapacket_id = 0
        time_gamp = flow.oper_time / total_packets
        while flow.num_packets >= 0:
                if datapacket_id % 500 == 0 or datapacket_id == total_packets:
                    print('EVENT: UE',self.ue_id,"Send DataPacket", datapacket_id,'/',total_packets,'to',flow.dest_id, 'at', self.env.now)
                current_time = self.env.now
                packet = DataPacket(flow.src_id, flow.dest_id, flow.dest_node_id, flow.flow_id, datapacket_id, current_time, flow.ack, 'up') #src_host_id, dest_host_id, flow_id, packetnum, timestamp
                key = (datapacket_id, flow.flow_id)
                self.data_packet_time[key] = current_time
                self.send_to_dest(packet, flow.dest_id)
                datapacket_id += 1
                flow.num_packets -= 1
                yield self.env.timeout(time_gamp)
        if flow.ack == 'y':
            print('EVENT: All The Data Packet of Flow Id', flow.flow_id, 'Has Been Sent, It Will Have Ack Packet')
        else:
            print('EVENT: All The Data Packet of Flow Id', flow.flow_id, 'Has Been Sent, It Will Have No Ack Packet')

    def start_radar_routing(self):
        tag = 0
        while True:
            #print("EVENT: UE", self.ue_id, "Start Radar Routing at", self.env.now)
            packet = RadarPacket(self.ue_id, tag)
            self.send_to_all_expect(packet)
            yield self.env.timeout(5)
            tag += 1

