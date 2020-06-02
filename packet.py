import simpy


class Packet(object):
    def __init__(self):
        super(Packet, self).__init__()

class RadarPacket(Packet):
    def __init__(self, src_host_id, tag):
        self.src_host_id = src_host_id
        self.tag = tag

    def router_receive_packet(self, router, last_port_id):
        src_host_id = self.src_host_id
        router_tag_table = router.radar_tag_table
        tag = self.tag
        if src_host_id not in router_tag_table or router_tag_table[
            src_host_id] < tag:  ## the radar message come here first time or need to update the information
            router_tag_table[src_host_id] = tag
            router.backwardspacket[src_host_id] = last_port_id
            router.send_to_all_expect(self, last_port_id)

    def host_receive_packet(self, host, last_port_id):
        print('host receives the Radar packet ', host.host_id)
        host.send_to_all_expect(EchoPacket(self.src_host_id, host.host_id, self.tag))

    def link_receive_packet(self, link, last_port_id):
        link.send_to_all_expect(self, last_port_id)


class EchoPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, tag):
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.tag = tag

    def router_receive_packet(self, router, last_port_id):
        src_host_id = self.src_host_id
        router_tag_table = router.radar_tag_table
        tag = self.tag
        if src_host_id in router_tag_table and router_tag_table[src_host_id] == tag:
            router.forwardspaceket[self.dest_host_id] = last_port_id
            router.send(router.backwardspacket[src_host_id], self)

    def host_receive_packet(self, host, last_port_id):
        print('host receives the Echo packet ', host.host_id)

    def link_receive_packet(self, link, last_port_id):
        link.send_to_all_expect(self, last_port_id)

class DataPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, flow_id, packetnum, timestamp):  # src/dest host id, flow id, pack number, time stamp
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.flow_id = flow_id
        self.packet_no = packetnum
        self.timestamp = timestamp

    def router_receive_packet(self, router, last_port_id):
        router.send(self, router.look_up(self.dest_host_id))

    def host_receive_packet(self, host, last_port_id):
        acknum = host.get_packet(self.flow_id, self.packet_no)
        if acknum is not None:
            host.send_except(AckPacket(self.dest_host_id, self.src_host_id, self.flow_id, acknum, self.timestamp))  ##Stamp


class AckPacket(Packet):
    def __init__(self, src_host_id, dest_host_id, flow_id, packetnum, timestamp):
        self.src_host_id = src_host_id
        self.dest_host_id = dest_host_id
        self.flow_id = flow_id
        self.packet_no = packetnum
        self.timestamp = timestamp

    def router_receive_packet(self, router, last_port_id):
        router.send(self, router.look_up(self.dest_host_id))

    def host_receive_packet(self, host, last_port_id):
        host.handle_ack(self.flow_id, self.packet_no, self.timestamp)  ##Stamp

