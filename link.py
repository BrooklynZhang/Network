import simpy
import collections
from gui import create_the_graph

class Link(object):

    def __init__(self, env, link_id, rate, delay, buf_size, algorithm):
        self.env = env
        self.link_id = link_id
        self.rate = rate  # Mbps
        self.delay = delay  # Milliseconds
        self.buf_size = buf_size  # KB 2^10 Bytes
        self.algorithm = algorithm
        self.adj_ports = {}
        self.monitor = {}
        self.buffercable = {}
        self.running_time = 0
        self.env.process(self.report_packet_loss())

    def add_port(self, source_id, source_port):
        self.adj_ports[source_id] = source_port
        self.buffercable[source_id] = BufferedCable(self,
                                                    source_id)  # For each direction, add a bufferedcable to handle the data

    def get_link_id(self):
        return self.link_id

    def monitoring(self):
        while True:
            keys = list(self.adj_ports.keys())
            for key in keys:
                buffer = self.buffercable[key]
                level = buffer.level[1].level
                self.monitor[key].append((self.env.now, level))
            if self.running_time - 0.002 <= self.env.now <= self.running_time - 0.001:
                create_the_graph(self.link_id, self.monitor)
            yield self.env.timeout(0.001)

    def monitor_process(self, timestamp):
        self.running_time = timestamp
        keys = list(self.adj_ports.keys())
        for key in keys:
            self.monitor[key] = [(self.env.now, 0)]
        self.env.process(self.monitoring())

    def receive(self, packet, source_id):
        if self.algorithm == 'ant':
            if packet.head == 'f':
                packet.stack_list.append(self.link_id)
            elif packet.head == 'b':
                packet.path.pop()
        self.buffercable[source_id].add_packet(packet)

    def report_packet_loss(self):
        while True:
            keys = list(self.adj_ports.keys())
            for key in keys:
                buffer = self.buffercable[key]
                packetloss = buffer.total_packet_loss
                if packetloss > 1:
                    print("WARNING: Link", self.link_id, "has total packet loss of", packetloss, 'at time', self.env.now)
            yield self.env.timeout(1)

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
        self.rate = float(link.rate)  # Mbps
        self.delay = float(link.delay)  # Milliseconds
        self.buf_size = 1.0E3 * int(link.buf_size)  # KB to Bytes
        self.packet_loss = {}
        self.total_packet_loss = 0
        self.packet_queue = collections.deque()  # Save the Data Packet
        self.level = (  # Modelling the production and consumption of a homogeneous,
            # undifferentiated bulk.
            simpy.Container(self.env, capacity=self.buf_size),
            simpy.Container(self.env, capacity=self.buf_size)
        )

        self.cable = simpy.Store(self.env)
        self.env.process(self.data_fill_cable())

    def add_packet(self, packet):
        self.env.process(self.add_packets(packet))

    def add_packets(self, packet):
        with self.level[0].put(packet.size) as req:  #
            ret = yield req | self.env.event().succeed()  # To trigger an event and mark it as successful,
                            # As a shorthand for AnyOf
            if req in ret:
                self.level[1].put(packet.size)
                self.packet_queue.append(packet)
            else:
                if hasattr(packet, 'flow_id'):
                    # self.packet_loss[packet.flow_id] += 1
                    self.total_packet_loss += 1

    def data_fill_cable(self):  # Sending Packet Mechanism
        while True:  # Once the Queue has data packet, it will get it and send out.
            yield self.level[1].get(1)
            packet = self.packet_queue.popleft()
            yield self.level[1].get(packet.size - 1)
            yield self.env.timeout(packet.size * 8  # Sending time for each Packet, if the Rate is set to 20 Mbps,
                                   / (self.rate * 1.0E6))  # a empty buffer link needs 0.0004 s to transfer a 1024 B
            # Data Packet
            yield self.level[0].get(packet.size)
            self.env.process(self.delay_fun(packet))

    def delay_fun(self, packet):
        yield self.env.timeout(self.delay / 1.0E3)  # Each Data Packet will have a latency.
                                                    # If all the conditions are same, long path will have more latency
        self.link.send_to_all_expect(packet, self.src_id)

