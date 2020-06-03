import simpy
import collections

class Link(object):

    def __init__(self, env, link_id, rate, delay, buf_size):
        self.env = env
        self.link_id = link_id
        self.rate = rate
        self.delay = delay
        self.buf_size = buf_size

        self.adj_ports = {}
        self.buffercable = {}

    def get_link_id(self):
        return self.link_id

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception("ERROR: Duplicate port name")
        self.adj_ports[source_id] = source_port

        #self.buffercable[source_id] = BufferedCable(self, source_id)

    def receive(self, packet, source_id):
        if packet.head == 'r':
            self.send_to_all_expect(packet, source_id)

        elif packet.head == 'e':
            self.send_to_all_expect(packet, source_id)

        #self.buffercable[source_id].add_packet(packet)

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.link_id)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)


class BufferedCable(object):

    def __init__(self, link, source_id):
        self.src_id = source_id
        self.link = link
        self.env = link.env
        self.link_id = link.link_id
        self.rate = link.rate
        self.delay = link.delay
        self.buf_size = 1000 * int(link.buf_size)

        self.packet_queue = collections.deque()
        self.level = simpy.Container(self.env, capacity=self.buf_size)


        self.cable = simpy.Store(self.env)
        self.env.process(self.data_fill_cable())

    def data_fill_cable(self):
        while True:
            packet = self.packet_queue.popleft()
            yield self.level.get(packet.size)
            yield self.env.timeout(packet.size * 8 / (self.rate * 1.0E6))
            self.env.process(self.delayfun(packet))

    def delayfun(self, packet):
        yield self.env.timeout(self.delay / 1.0E3)
        self.link.send_to_all_expect(packet, self.src_id)

    def add_packet(self, packet):
        self.env.process(self.add_packets(packet))

    def add_packets(self, packet):
        self.level.put(packet.size)
        self.packet_queue.append(packet)






