import simpy

class basicflow(object):
    def __init__(self, env, flow_id, src_id, dest_id, data_mb, start_s,state_constr, init_state):