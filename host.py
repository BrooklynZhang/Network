import simpy
from packet import RadarPacket

class Host(object):

    def __init__(self, env, host_id):
        self.env = env
        self.host_id = host_id
        self.adj_ports = {}
        self.env.process(self.start_radar_routing())

    def start_radar_routing(self):
        print("start radar routing", self.host_id)
        tag = 0
        while True:
            self.send_to_all_expect(RadarPacket(self.host_id, tag))
            yield self.env.timeout(5)
            tag += 1

    def get_host_id(self):
        return self.host_id

    def add_port(self, device_id, device_port):
        if device_id in self.adj_ports:
            raise Exception('Duplicate port name')
        self.adj_ports[device_id] = device_port

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.host_id)

    def receive(self, packet, source_id):
        packet.host_receive_packet(self, source_id)
