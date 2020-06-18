import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket, BackwardAnt, ForwardAnt
from collections import defaultdict

class IAB_Donor(object):

    def __init__(self, env, donor_id, algorithm):
        self.env = env
        self.donor_id = donor_id
        self.adj_ports = {}
        self.algorithm = algorithm
        self.timetable = defaultdict(int)
        self.monitor_transmission_t = {}
        self.monitor_data_act_time = {}
        self.data_packet_time = {}
        # self.env.process(self.start_radar_routing())

    def add_flow(self, flow):
        self.flows[flow.flow_id] = flow
        self.env.process(self.send_data_packets(flow))

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception('ERROR: Duplicate port name')
        self.adj_ports[source_id] = source_port

    def receive(self, packet, source_id):
        if packet.head == 'r':
            #print('EVENT: IAB_DONOR', self.donor_id, 'receive the data packet from', packet.src_host_id, 'at', self.env.now)
            self.send(source_id, EchoPacket(self.donor_id, packet.src_host_id, packet.tag))

        elif packet.head == 'e':
            print('EVENT: IAB_DONOR', self.donor_id, 'receives the Echo packet from', packet.dest_host_id, 'at', self.env.now)

        elif packet.head == 'd':
            time_gap = self.env.now - packet.timestamp
            if packet.flow_id in self.monitor_transmission_t:
                self.monitor_transmission_t[packet.flow_id].append((packet.packet_no, time_gap))
            else:
                self.monitor_transmission_t[packet.flow_id] = [(packet.packet_no, time_gap)]
            if packet.ack == 'y':
                if self.algorithm in ['q', 'ant', 'dijkstra']:
                    if packet.packet_no % 500 == 0:
                        print('EVENT: IAB Donor', self.donor_id,'received the data packet from', packet.src_host_id, 'with packet id of', packet.packet_no)
                self.send(source_id, AckPacket(packet.dest_host_id, packet.src_host_id, packet.src_node_id, packet.flow_id, packet.packet_no, self.env.now))
            else:
                if packet.packet_no % 500 == 0:
                    print('EVENT: IAB Donor', self.donor_id, 'received the data packet from', packet.src_host_id,
                          'with packet id of', packet.packet_no)
        elif packet.head == 'a':
            #print('EVENT: IAB Donor', self.donor_id, "send AckPacket to",packet.dest_host_id, 'with last iab of', packet.dest_node_id)
            pass
        elif packet.head == 'f':
            if packet.dest_host_id == self.donor_id:
                # print('EVENT: IAB Node', self.donor_id, 'received a forward ant from', packet.src_host_id,'at', self.env.now)
                foward_path = packet.stack_list
                next_port = foward_path.pop()
                stack = packet.stack
                stack[self.donor_id] = self.env.now
                backward_ant = BackwardAnt(self.donor_id, packet.src_host_id, foward_path, stack, packet.packet_no, packet.tag, self.env.now)
                self.send(next_port, backward_ant)

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.donor_id)

    def send_data_packets(self, flow):
        yield self.env.timeout(flow.start_s)
        print('EVENT: Adding flow to IAB Donor', self.donor_id, 'at', self.env.now)
        total_packets = flow.num_packets
        self.monitor_data_act_time[flow.flow_id] = []
        datapacket_id = 0
        time_gamp = flow.oper_time / total_packets
        while flow.num_packets >= 0:
                if datapacket_id % 500 == 0 or datapacket_id == total_packets:
                    print('EVENT: IAB DONOR',self.donor_id,"Send DataPacket", datapacket_id,'/',total_packets,'to',flow.dest_id)
                current_time = self.env.now
                packet = DataPacket(flow.src_id, flow.dest_id, flow.flow_id, datapacket_id, current_time, flow.ack) #src_host_id, dest_host_id, flow_id, packetnum, timestamp
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

    def send_to_dest(self, packet, dest_id):
        if self.algorithm == 'dijkstra':
            next_jump_port = self.timetable[dest_id][0]
            self.send(next_jump_port, packet)
        elif self.algorithm in ['q', 'ant']:
            self.send_to_all_expect(packet)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def start_radar_routing(self):
        print('EVENT: IAB', self.donor_id, 'Start Radar Routing at', self.env.now)
        tag = 0
        while True:
            self.send_to_all_expect(RadarPacket(self.donor_id, tag))
            yield self.env.timeout(5)
            tag += 1
