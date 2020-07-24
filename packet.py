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
    def __init__(self, src_host_id, dest_host_id, flow_id, packetnum, timestamp, ack, direction, route = None):  # src/dest host id, flow id, pack number, time stamp
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
        self.current_timestamp = None
        self.direction = direction
        self.route = route


class AckPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, dest_node_id, flow_id, packetnum, timestamp, direction):
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
        self.current_timestamp = None
        self.direction = direction


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


class InformationPacket(Packet):
    def __init__(self, dest_host_id , id, reward, flow_id, done = 0):
        self.head = 'i'
        self.id = id
        self.dest_host_id = dest_host_id
        self.reward = reward
        self.size = 4
        self.done = done
        self.flow_id = flow_id


class HelloPacket(Packet):
    def __init__(self, ue_id):
        self.head = 'h'
        self.ue_id = ue_id
        self.size = 4


class HelloPacketD(Packet):
    def __init__(self, donor_id):
        self.head = 'h-d'
        self.donor_id = donor_id
        self.size = 4


class HelloPacketI(Packet):
    def __init__(self, iab_id, time):
        self.head = 'h-i'
        self.iab_id = iab_id
        self.time_stamp = time
        self.size = 4


class level_packet(Packet):
    def __init__(self, node_id, level, jump=0):
        self.head = 'l'
        self.node_id = node_id
        self.level = level
        self.size = 4
        self.jump = jump
        self.tag = 0

    def setjump(self, newjump):
        self.jump = newjump


class Packetlossinfo(Packet):
    def __init__(self, node_id, dest_host_id, flow_id):
        self.head = 'p'
        self.id = node_id
        self.flow_id = flow_id
        self.dest_host_id = dest_host_id
        self.size = 4

class Usage_report(Packet):
    def __init__(self, link_id, level, tag):
        self.head = 'U'
        self.id = link_id
        self.level = level
        self.jump = 6
        self.tag = tag

class RREQ(Packet):
    def __init__(self, id, source_id, dest_id, time, tag, jump=10):
        self.head = 'RREQ'
        self.id = id
        self.source_id = source_id
        self.dest_id = dest_id
        self.stack = {source_id: time}
        self.path = [source_id]
        self.tag = tag
        self.size = 4
        self.jump = jump

class Broadcast(Packet):
    def __init__(self, source_id, dest_id, stack, path, tag, jump):
        self.head = 'broad'
        self.source_id = source_id
        self.dest_id = dest_id
        self.stack = stack
        self.path = path
        self.tag = tag
        self.size = 4
        self.jump = jump

class RREP(Packet):
    def __init__(self, source_id, dest_id, time_table, tag, path):
        self.head = 'RREP'
        self.source_id = source_id
        self.dest_id = dest_id
        self.time_table = time_table
        self.tag = tag
        self.size = 4
        self.path = path