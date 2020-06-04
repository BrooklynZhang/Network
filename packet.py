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


class EchoPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, tag):
        self.head = 'e'
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.tag = tag
        self.size = 64
        self.path = [dest_host_id]

    def add_path(self, id):
        self.path.append(id)


class DataPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, flow_id, packetnum, timestamp):  # src/dest host id, flow id, pack number, time stamp
        self.head = 'd'
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.flow_id = flow_id
        self.packet_no = packetnum
        self.timestamp = timestamp
        self.size = 1024


class AckPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, flow_id, packetnum, timestamp):
        self.head = 'e'
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.flow_id = flow_id
        self.packet_no = packetnum
        self.timestamp = timestamp
        self.size = 64

    def host_receive_packet(self, host, last_port_id):
        host.handle_ack(self.flow_id, self.packet_no, self.timestamp)  ##Stamp

