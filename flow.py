import simpy

class BaseFlow(object):
    def __init__(self, env, flow_id, src_id, dest_id, data_mb, start_s,state_constr, init_state):
        self.env = env
        self.flow_id = flow_id
        self.src_id = src_id
        self.dest_id = dest_id
        self.data_mb = data_mb
        self.start_s = start_s
        self.state_constra = state_constr
