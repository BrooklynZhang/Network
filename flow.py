import simpy
from math import ceil
from packet import DataPacket

class BaseFlow(object):
    def __init__(self, env, flow_id, src_id, dest_id, data_mb, start_s, algorithm, ack):
        self.env = env
        self.flow_id = flow_id
        self.src_id = src_id
        self.dest_id = dest_id
        self.algorithm = algorithm
        self.data_mb = float(data_mb)
        self.start_s = float(start_s)
        self.num_packets = int(ceil(float(data_mb) * 1.0E6 / 1024))
        self.packet_pool = simpy.Store(env)
        self.ack = ack