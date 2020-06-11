import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket, ForwardAnt, BackwardAnt

import numpy as np


class IAB_Node(object):

    def __init__(self, env, node_id, algorithm):
        self.env = env
        self.node_id = node_id
        self.adj_ports = {}
        self.algorithm = algorithm
        self.iab_id_list = []
        self.adj_ues = {}

        if self.algorithm == 'dijkstra':
            self.radar_tag_table = {}
            self.backwardspacket = {}
            self.forwardspaceket = {}

        if self.algorithm == 'q':
            self.time_stamp_table = {}
            self.q_routing_table = {}
            self.q_routing_back_table = {}
            self.discount_factor = 0.9
            self.learning_rate = 0.1
            self.epsilon = 0.1

        if self.algorithm == 'ant':
            self.threshold = float(0.0)
            self.iteration = 10
            self.ants_num = 1000
            self.pheromones_table = {}  # Routing Table, it has the probabilities P(i,n) which express the goodness
            # of choosing n as next node when the destination is i, current, it only have one destination - iab donor
            self.trip = [0.0, 0.0, []]  # estimates of mean values and variances from node k to iab donor
            self.c = 2

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception("ERROR: Duplicate port name")
        self.adj_ports[source_id] = source_port

    def ant_select_port(self, ant_packet, source_id):
        dest_pheromones_table = self.pheromones_table[ant_packet.dest_host_id].copy()
        del dest_pheromones_table[source_id]  #
        if dest_pheromones_table == {}:
            print('WARNING: No Path Anymore')
            return None
        else:
            ports_id_list = list(dest_pheromones_table.keys())
            prob_list = np.copy(list(dest_pheromones_table.values()))
            norm_prob = prob_list / prob_list.sum()
            next_port_id_list = np.random.choice(ports_id_list, 1, p=norm_prob)
            next_port_id = next_port_id_list[0]
            if next_port_id not in ant_packet.visited:
                return next_port_id
            else:
                next_port_id_list = np.random.choice(ports_id_list, 1)
                next_port_id = next_port_id_list[0]
                return next_port_id

    def calculate_reward(self, packet):
        future_reward = packet.reward
        key = (packet.packet_no, packet.flow_id)
        delay = self.env.now - self.time_stamp_table[
            key]  # The shorter the delay, the larger the reward example 0.11383424000000031
        reward = future_reward - (100 * delay)
        return reward

    def data_ant_select_port(self, dest_id, source_id):
        dest_pheromones_table = self.pheromones_table[dest_id].copy()
        del dest_pheromones_table[source_id]
        ports_id_list = list(dest_pheromones_table.keys())
        prob_list = np.copy(list(dest_pheromones_table.values()))
        norm_prob = prob_list / prob_list.sum()
        next_port_id_list = np.random.choice(ports_id_list, 1, p=norm_prob)
        next_port_id = next_port_id_list[0]
        return next_port_id

    def get_action(self):
        if np.random.rand() < self.epsilon:
            action = np.random.choice(list(self.q_routing_table.keys()))
        else:
            action = max(self.q_routing_table, key=self.q_routing_table.get)
        return action

    def initialize(self):
        if self.algorithm == 'q':
            for port in self.adj_ports:
                self.q_routing_table[port] = 0
        if self.algorithm == 'ant':
            self.env.process(self.start_ant_colony_algorithm())

    def normalization(self, dest_id):
        dest_pheromones_table = self.pheromones_table[dest_id].copy()
        keys = list(dest_pheromones_table.keys())
        values = dest_pheromones_table.values()
        norm = [float(i) / sum(values) for i in values]
        for i in range(len(keys)):
            dest_pheromones_table[keys[i]] = norm[i]
        self.pheromones_table[dest_id] = dest_pheromones_table

    def receive(self, packet, source_id):
        if packet.head == 'r':
            if self.algorithm == 'dijkstra' or self.algorithm == 'q':
                src_host_id = packet.src_host_id
                router_tag_table = self.radar_tag_table
                tag = packet.tag
                if src_host_id not in router_tag_table or router_tag_table[
                    src_host_id] < tag:  ## the radar message come here first time or need to update the information
                    router_tag_table[src_host_id] = tag
                    self.backwardspacket[src_host_id] = source_id
                    self.send_to_all_expect(packet, source_id)

        elif packet.head == 'e':
            if self.algorithm == 'dijkstra' or self.algorithm == 'q':
                dest_host_id = packet.dest_host_id
                router_tag_table = self.radar_tag_table
                tag = packet.tag
                if dest_host_id in router_tag_table and router_tag_table[dest_host_id] == tag:
                    self.forwardspaceket[packet.src_host_id] = source_id
                    packet.add_path(self.node_id)
                    self.send(self.backwardspacket[dest_host_id], packet)

        elif packet.head == 'd':
            if packet.src_host_id not in list(self.adj_ues.keys()):
                self.adj_ues[packet.src_host_id] = source_id
            if packet.src_node_id == None:
                packet.src_node_id = self.node_id
            if self.algorithm == 'dijkstra':
                self.send(self.search_next_jump_forward(packet.dest_host_id), packet)
            elif self.algorithm == 'q':
                action = self.get_action()
                key = (packet.packet_no, packet.flow_id)
                self.q_routing_back_table[key] = source_id
                self.time_stamp_table[key] = self.env.now
                self.send(action, packet)
            elif self.algorithm == 'ant':
                next_port = self.data_ant_select_port(packet.dest_host_id, source_id)
                self.send(next_port, packet)

        elif packet.head == 'a':
            if self.algorithm == 'dijkstra':
                self.send(self.search_next_jump_backward(packet.dest_host_id), packet)
            elif self.algorithm == 'q':
                self.updating_q_routing_table(packet, source_id)
                key = (packet.packet_no, packet.flow_id)
                self.send(self.q_routing_back_table[key], packet)
            elif self.algorithm == 'ant':
                if packet.dest_host_id in list(self.adj_ues.keys()):
                    next_port = self.adj_ues[packet.dest_host_id]
                else:
                    next_port = self.data_ant_select_port(packet.dest_node_id, source_id)
                self.send(next_port, packet)

        elif packet.head == 'f':
            if packet.dest_host_id == self.node_id:
                foward_path = packet.stack_list
                next_port = foward_path.pop()
                stack = packet.stack
                stack[self.node_id] = self.env.now
                backward_ant = BackwardAnt(self.node_id, packet.src_host_id, foward_path, stack, packet.packet_no,
                                           packet.tag, self.env.now)
                self.send(next_port, backward_ant)
            else:
                if self.node_id in packet.stack_list:
                    loc = packet.stack_list.index(self.node_id)
                    pop_list = packet.stack_list[(loc + 1):]
                    for e in pop_list:
                        if e in list(packet.stack.keys()):
                            del packet.stack[e]
                    packet.stack_list = packet.stack_list[:loc + 1]
                    packet.visited.append(self.node_id)
                else:
                    packet.visited.append(self.node_id)
                    packet.stack_list.append(self.node_id)
                    if packet.stack. __contains__(self.node_id):
                        print('ERROR: Cycle Detected')
                    packet.stack[self.node_id] = self.env.now
                next_port = self.ant_select_port(packet, source_id)

                if next_port is not None:
                    self.send(next_port, packet)

        elif packet.head == 'b':
            self.update_the_trip_list(packet)
            self.update_the_pheromones(packet, source_id)
            if packet.dest_host_id == self.node_id:
                #print('EVENT:', self.node_id, 'receives its backforward ant #', packet.packet_no,'with tag of', packet.tag)
                pass
            else:
                next_port = packet.path.pop()
                self.send(next_port, packet)

    def search_next_jump_forward(self, dest_id):
        if dest_id in self.forwardspaceket:
            return self.forwardspaceket[dest_id]
        else:
            raise Exception("ERROR: Can not find forwarding path", self.node_id)
            return None

    def search_next_jump_backward(self, dest_id):
        if dest_id in self.backwardspacket:
            return self.backwardspacket[dest_id]
        else:
            raise Exception("ERROR: Can not find forwarding path", self.node_id)
            return None

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.node_id)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def start_ant_colony_algorithm(self):
        # print('EVENT: IAB Node',self.node_id ,"Start ACO Routing at", self.env.now, self.adj_ports)
        nk = len(self.adj_ports)
        self.threshold = 1 / (nk * 5)
        for iab_id in self.iab_id_list:
            if self.node_id != iab_id:
                dict_pheromones = {}
                for ports in list(self.adj_ports.keys()):
                    dict_pheromones[ports]= 1 / nk
                self.pheromones_table[iab_id] = dict_pheromones
        tag = 0
        while True:
            id = 0
            while id < self.ants_num:
                dest_host_id = np.random.choice(self.iab_id_list, 1)
                if dest_host_id == self.node_id:
                    continue
                forward_ant_packet = ForwardAnt(self.node_id, dest_host_id[0], id, tag)
                forward_ant_packet.stack[self.node_id] = self.env.now
                next_port_id = np.random.choice(list(self.pheromones_table[dest_host_id[0]].keys()), 1)
                self.send(next_port_id[0], forward_ant_packet)
                id += 1
            yield self.env.timeout(5)
            tag += 1

    def update_the_pheromones(self, packet, source_id):
        dest_pheromones_table = self.pheromones_table[packet.src_host_id].copy()
        prob = dest_pheromones_table[source_id]
        time_gap = self.env.now - packet.stack[self.node_id]
        dimensionless_measure = time_gap / (self.c * self.trip[0])
        if dimensionless_measure >= 1:
            dimensionless_measure = 1
        new_p = prob + (1 - dimensionless_measure) * (1 - prob)
        for key in list(dest_pheromones_table.keys()):
            res = dest_pheromones_table[key] - (1 - dimensionless_measure) * dest_pheromones_table[key]
            #if res < self.threshold:
            #    res = 0.0
            dest_pheromones_table[key] = res
        dest_pheromones_table[source_id] = new_p
        self.pheromones_table[packet.src_host_id] = dest_pheromones_table
        self.normalization(packet.src_host_id)

    def update_the_trip_list(self, packet):
        avg_time = self.trip[0]
        all_values = self.trip[2]
        forward_ant_time = packet.stack[self.node_id]
        time_gap = self.env.now - forward_ant_time
        count = len(all_values)
        new_avg_time = (avg_time * count + time_gap) / (count + 1)
        all_values.append(time_gap)
        var = 0
        for x in all_values:
            var += (x - new_avg_time) ** 2
        new_var = var / (count + 1)
        self.trip = [new_avg_time, new_var, all_values]

    def updating_q_routing_table(self, packet, source_id):
        reward = self.calculate_reward(packet)
        current_q = self.q_routing_table[source_id]
        max_q = max(self.q_routing_table, key=self.q_routing_table.get)
        new_q = reward + self.discount_factor * self.q_routing_table[max_q]
        self.q_routing_table[source_id] += self.learning_rate * (new_q - current_q)
