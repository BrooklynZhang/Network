import simpy
from packet import RadarPacket, EchoPacket

class Router(object):

    def __init__(self, env, router_id):

        self.env = env
        self.router_id = router_id
        self.adj_ports = {}
        self.link_id_to_dest = {}
        self.radar_tag_table = {}
        self.backwardspacket = {}
        self.forwardspaceket = {}

    def get_host_id(self):
        return self.host_id

    def add_port(self, device_id, device_port):
        if device_id in self.adj_ports:
            raise Exception("ERROR: Duplicate port name")
        self.adj_ports[device_id] = device_port

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.router_id)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def receive(self, packet, source_id):
        packet.router_receive_packet(self, source_id)

    def search_next_jump(self, dest_id):
        if dest_id in self.forwardspaceket:
            return self.forwardspaceket[dest_id]
        else:
            raise Exception("ERROR: Can not find forwarding path")
            return None


