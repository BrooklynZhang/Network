import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket

class IAB_Donor(object):

    def __init__(self, env, donor_id):
        self.env = env
        self.donor_id = donor_id
        self.adj_ports = {}
        #self.env.process(self.start_radar_routing())

    def start_radar_routing(self):
        print("start radar routing", self.donor_id)
        tag = 0
        while True:
            self.send_to_all_expect(RadarPacket(self.donor_id, tag))
            yield self.env.timeout(5)
            tag += 1

    def get_host_id(self):
        return self.donor_id

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception('Duplicate port name')
        self.adj_ports[source_id] = source_port

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.donor_id)

    def receive(self, packet, source_id):
        if packet.head == 'r':
            print('IAB_DONOR', self.donor_id, 'receive the data packet from', packet.src_host_id)
            self.send(source_id, EchoPacket(packet.src_host_id, self.donor_id, packet.tag))

        elif packet.head == 'e':
            print('IAB_DONOR', self.donor_id, 'receives the Echo packet from', packet.dest_host_id)

        elif packet.head == 'd':
            acknum = self.get_packet(packet.flow_id, packet.packet_no)
            if acknum is not None:
                self.send_except(AckPacket(packet.dest_host_id, packet.src_host_id, packet.flow_id, acknum, packet.timestamp))

        elif packet.head == 'a':
            self.handle_ack(packet.flow_id, packet.packet_no, packet.timestamp)