import simpy


class Packet(object):
    def __init__(self):
        super(Packet, self).__init__()


class RadarPacket(Packet):
    def __init__(self, src_host_id, tag):
        self.head = 'r'
        self.src_host_id = src_host_id
        self.tag = tag
        self.size = 64
        self.link_timestamp = None


class EchoPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, tag):
        self.head = 'e'
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.tag = tag
        self.size = 64
        self.path = [src_host_id]
        self.link_timestamp = None

    def add_path(self, id):
        self.path.append(id)


class DataPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, flow_id, packetnum, timestamp, ack):  # src/dest host id, flow id, pack number, time stamp
        self.head = 'd'
        self.src_host_id = src_host_id
        self.src_node_id = None
        self.dest_host_id = dest_host_id
        self.flow_id = flow_id
        self.packet_no = packetnum
        self.timestamp = timestamp
        self.size = 1024
        self.ack = ack
        self.link_timestamp = None


class AckPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, dest_node_id, flow_id, packetnum, timestamp):
        self.head = 'a'
        self.src_host_id = src_host_id
        self.dest_node_id = dest_node_id
        self.dest_host_id = dest_host_id
        self.flow_id = flow_id
        self.packet_no = packetnum
        self.timestamp = timestamp
        self.size = 64
        self.reward = 100
        self.link_timestamp = None


class ForwardAnt(Packet):
    def __init__(self, src_host_id, dest_host_id, packet_id, version):
        self.head = 'f'
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.tag = version
        self.packet_no = packet_id
        self.stack = {}
        self.visited = []
        self.stack_list = []
        self.size = 64
        self.link_timestamp = None


class BackwardAnt(Packet):
    def __init__(self, src_host_id, dest_host_id, path, stack, packet_id, tag, time):
        self.head = 'b'
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.packet_no = packet_id
        self.tag = tag
        self.path = path
        self.stack = stack
        self.size = 64
        self.time_stamp = time
        self.link_timestamp = None
