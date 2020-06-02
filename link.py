import simpy

class Link(object):
    def __init__(self, env, source_id, dest_id,  link_id, rate, delay):
        self.env = env
        self.source_id = source_id
        self.dest_id = dest_id
        self.link_id = link_id
        self.rate = rate
        self.delay = delay

        self.adj_ports = {}

    def get_link_id(self):
        return self.link_id

    def add_port(self, device_id, device_port):
        if device_id in self.adj_ports:
            raise Exception("ERROR: Duplicate port name")
        self.adj_ports[device_id] = device_port

    def receive(self, packet, source_id):
        packet.link_receive_packet(self, source_id)

    def send(self, dest_id, packet):
        self.adj_ports[dest_id].receive(packet, self.link_id)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)