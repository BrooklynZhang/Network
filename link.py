import simpy
import collections


class Link(object):

    def __init__(self, env, link_id, rate, delay, buf_size, algorithm):
        self.env = env
        self.link_id = link_id
        self.rate = rate            #Mbps
        self.delay = delay          #Milliseconds
        self.buf_size = buf_size    #KB 2^10 Bytes
        self.algorithm = algorithm
        self.adj_ports = {}
        self.buffercable = {}
        self.env.process(self.reprot_packet_loss())

    def reprot_packet_loss(self):
        while True:
            keys = list(self.adj_ports.keys())
            for key in keys:
                buffer = self.buffercable[key]
                packetloss = buffer.total_packet_loss
                if packetloss > 1:
                    print("Link", self.link_id, "has total packet loss of", packetloss,'at time', self.env.now)
            yield self.env.timeout(1)

    def get_link_id(self):
        return self.link_id

    def add_port(self, source_id, source_port):
        self.adj_ports[source_id] = source_port
        self.buffercable[source_id] = BufferedCable(self, source_id)

    def receive(self, packet, source_id):
        self.buffercable[source_id].add_packet(packet)

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
        self.rate = float(link.rate)                #Mbps
        self.delay = float(link.delay)              #Milliseconds
        self.buf_size = 1.0E3 * int(link.buf_size)   # KB to Bytes
        self.packet_loss = {}
        self.total_packet_loss = 0
        self.packet_queue = collections.deque()     #Save the Data Packet
        self.level = (
            simpy.Container(self.env, capacity=self.buf_size),
            simpy.Container(self.env, capacity=self.buf_size)
        )

        self.cable = simpy.Store(self.env)
        self.env.process(self.data_fill_cable())

    def data_fill_cable(self):
        while True:
            yield self.level[1].get(1)
            packet = self.packet_queue.popleft()
            yield self.level[1].get(packet.size - 1)
            yield self.env.timeout(packet.size * 8 / (self.rate * 1.0E6))
            yield self.level[0].get(packet.size)
            '''print('{:06f} buffer_diff g {} {}'.format(
                self.env.now,
                self.link_id,
                -1 * packet.size))
            print('{:06f} transmission {} {}'.format(
                self.env.now,
                self.link_id,
                packet.size))'''

            self.env.process(self.delay_fun(packet))

    def delay_fun(self, packet):
        yield self.env.timeout(self.delay / 1.0E3)
        self.link.send_to_all_expect(packet, self.src_id)

    def add_packet(self, packet):
        self.env.process(self.add_packets(packet))

    def add_packets(self, packet):
        with self.level[0].put(packet.size) as req:
            ret = yield req | self.env.event().succeed()
            if req in ret:
                self.level[1].put(packet.size)
                self.packet_queue.append(packet)
                '''print('{:06f} buffer_diff p {} {}'.format(
                    self.env.now,
                    self.link_id,
                    packet.size))'''
            else:
                if hasattr(packet, 'flow_id'):
                    '''print('{:06f} packet_loss {} {} {}'.format(
                        self.env.now,
                        self.link_id,
                        packet.flow_id,
                        packet.packet_no))'''
                    #self.packet_loss[packet.flow_id] += 1
                    self.total_packet_loss += 1




