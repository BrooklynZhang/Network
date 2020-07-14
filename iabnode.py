import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket, ForwardAnt, BackwardAnt, InformationPacket, level_packet, HelloPacketI
from dqn_model import INPUT_NN, DQN, ReplayBuffer
import collections
import torch
import torch.optim as optim
import numpy as np
import random
import copy
from torch.autograd import Variable


class IAB_Node(object):

    def __init__(self, env, node_id, algorithm):
        self.env = env
        self.node_id = node_id
        self.adj_ues = {}
        self.adj_ports = {}
        self.adj_iab = {}
        self.adj_donors = {}
        self.algorithm = algorithm
        self.iab_id_list = []
        self.packet_queue = collections.deque()
        self.node_usage = (
            simpy.Container(self.env, capacity=1.0E9),
            simpy.Container(self.env, capacity=1.0E9)
        )
        self.replay_buffer = []

        if self.algorithm == 'dijkstra':
            self.radar_tag_table = {}
            self.backwardspacket = {}
            self.forwardspaceket = {}
            # self.env.process(self.start_radar_routing())

        if self.algorithm == 'q':
            self.q_routing_table = {}
            self.learning_rate = 0.1
            self.epsilon = 0.1

        if self.algorithm == 'ant':
            self.threshold = float(0.0)
            self.iteration = 10
            self.ants_num = 1000
            self.pheromones_table = {}  # Routing Table, it has the probabilities P(i,n) which express the goodness
            # of choosing n as next node when the destination is i, current, it only have one destination - iab donor
            # self.andict_t_pheromones = {}
            self.trip = [0.0, 0.0, []]  # estimates of mean values and variances from node k to iab donor
            self.c = 2

        if self.algorithm == 'dqn':
            self.bufffer_size = int(1e3)
            self.batch_size = 16
            self.discount = 0.9
            self.TAU = 1e-3
            self.lr = 0.05
            self.update_freq = 1

            self.epsilon = 0.1

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.input_size = 128
            self.hidden_size = 128
            self.output_size = 32

            self.actions = []
            self.num_actions_hist = 2000
            self.num_future_dest = 20
            self.actions_hist = []
            self.neighbor_info = []
            self.packet_queue_dest = collections.deque()
            self.saved_state_action = {}

            self.model_local = None
            self.action_size = None
            self.optimizer = None
            self.memory = None

            #lstm
            self.hidden0 = None
            self.hidden1 = None

    def add_packets(self, dest_ports, packet):
        with self.node_usage[0].put(1) as req:
            ret = yield req | self.env.event().succeed()
            if req in ret:
                self.packet_queue.append((dest_ports, packet))
                self.node_usage[1].put(1)
            else:
                print("ERROR: IAB Node meets Congestion")

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception("ERROR: Duplicate port name")
        self.adj_ports[source_id] = source_port
        self.env.process(self.sending_out_packets())

    def ant_select_port(self, ant_packet, source_id):
        dest_pheromones_table = copy.deepcopy(self.pheromones_table[ant_packet.dest_host_id])
        del dest_pheromones_table[source_id]  #
        if dest_pheromones_table == {}:
            print('WARNING: No Path Anymore')
            return None
        else:
            ports_id_list = list(dest_pheromones_table.keys())
            prob_list = np.copy(list(dest_pheromones_table.values()))
            norm_prob = prob_list / prob_list.sum()
            # need to modify
            flag = False
            for i in norm_prob:
                if np.isnan(i):
                    flag = True

            if not flag:
                norm_prob = [1.0 / len(ports_id_list)] * len(ports_id_list)

                for i in list(dest_pheromones_table.keys()):
                    self.pheromones_table[ant_packet.dest_host_id][i] = 1.0 / len(ports_id_list)
            #
            next_port_id_list = np.random.choice(ports_id_list, 1, p=norm_prob)
            next_port_id = next_port_id_list[0]
            if next_port_id not in ant_packet.visited:
                return next_port_id
            else:
                next_port_id_list = np.random.choice(ports_id_list, 1)
                next_port_id = next_port_id_list[0]
                return next_port_id

    def data_ant_select_port(self, dest_id, source_id):
        dest_pheromones_table = copy.deepcopy(self.pheromones_table[dest_id])
        del dest_pheromones_table[source_id]
        ports_id_list = list(dest_pheromones_table.keys())
        prob_list = np.copy(list(dest_pheromones_table.values()))
        norm_prob = prob_list / prob_list.sum()
        next_port_id_list = np.random.choice(ports_id_list, 1, p=norm_prob)
        return next_port_id_list[0]

    def delay_fun(self, port, packet):
        yield self.env.timeout(1 / 1.0E6)
        self.adj_ports[port].receive(packet, self.node_id)

    def exchange_info(self):
        num_dest = len(self.iab_id_list)
        self.neighbor_info = [0 for i in range(num_dest)]
        while True:
            packet = level_packet(self.node_id, self.node_usage[1].level)
            self.send_to_all_expect_direct(packet)
            yield self.env.timeout(0.05)

    def generate_q_routing_table(self, state, packet, source_id):
        self.q_routing_table[state] = {}
        if packet.direction == 'up':
            for port in self.adj_ports:
                if port not in list(self.adj_ues.values()):
                    self.q_routing_table[state][port] = np.random.rand() / 10
        elif packet.direction == 'down':
            for port in self.adj_ports:
                if port not in list(self.adj_ues.values()) and port not in list(self.adj_donors.values()):
                    self.q_routing_table[state][port] = np.random.rand() / 10

    def get_action(self, packet, source_id):
        if packet.direction == 'up':
            state = packet.dest_host_id
        elif packet.direction == 'down':
            state = packet.dest_node_id
        if state not in self.q_routing_table:
            self.generate_q_routing_table(state, packet, source_id)
        random = np.random.rand()
        if random > self.epsilon:
            action = min(self.q_routing_table[state], key=self.q_routing_table[state].get)
        else:
            action = np.random.choice(list(self.q_routing_table[state]))
        return action

    def get_distribute_action(self, packet, source_id):
        if packet.direction == 'up':
            state = packet.dest_host_id
        elif packet.direction == 'down':
            state = packet.dest_node_id
        action_dict = self.q_routing_table[state].copy()
        ports_id_list = list(action_dict.keys())
        time_list = list(action_dict.values())
        prob_list = np.copy([1.0 / i for i in time_list])
        norm_prob = prob_list / prob_list.sum()
        next_port_id_list = np.random.choice(ports_id_list, 1, p=norm_prob)
        return next_port_id_list[0]

    def initialize(self):
        if self.algorithm == 'ant':
            self.env.process(self.start_ant_colony_algorithm())
        elif self.algorithm == 'dqn':
            self.env.process(self.exchange_info())

    def normalization(self, dest_id):
        dest_pheromones_table = copy.deepcopy(self.pheromones_table[dest_id])
        keys = list(dest_pheromones_table.keys())
        values = dest_pheromones_table.values()
        norm = [float(i) / sum(values) for i in values]
        for i in range(len(keys)):
            dest_pheromones_table[keys[i]] = norm[i]
        self.pheromones_table[dest_id] = copy.deepcopy(dest_pheromones_table)

    def receive(self, packet, source_id):
        if packet.head == 'h':
            if packet.ue_id not in list(self.adj_ues.keys()):
                self.adj_ues[packet.ue_id] = source_id

        if packet.head == 'h-d':
            if packet.donor_id not in list(self.adj_donors.keys()):
                self.adj_donors[packet.donor_id] = source_id


        elif packet.head == 'r':
            if self.algorithm == 'dijkstra' or self.algorithm == 'q':
                src_host_id = packet.src_host_id
                router_tag_table = self.radar_tag_table
                tag = packet.tag
                if src_host_id not in router_tag_table or router_tag_table[
                    src_host_id] < tag:  ## the radar message come here first time or need to update the information
                    router_tag_table[src_host_id] = tag
                    self.backwardspacket[src_host_id] = (source_id, tag)
                    self.send_to_all_expect(packet, source_id)

        elif packet.head == 'e':
            if self.algorithm == 'dijkstra' or self.algorithm == 'q':
                dest_host_id = packet.dest_host_id
                router_tag_table = self.radar_tag_table
                tag = packet.tag
                if dest_host_id in router_tag_table and router_tag_table[dest_host_id] == tag:
                    if dest_host_id in self.forwardspaceket and self.forwardspaceket[dest_host_id][1] == tag:
                        pass
                    else:
                        self.forwardspaceket[dest_host_id] = (source_id, tag)
                        packet.add_path(self.node_id)
                        self.send(self.backwardspacket[dest_host_id][0], packet)

        elif packet.head == 'd':
            if packet.src_node_id == None:
                packet.src_node_id = self.node_id
            if self.algorithm == 'dijkstra':
                self.send(self.search_next_jump_forward(packet.src_host_id), packet)
            elif self.algorithm == 'q':
                if packet.packet_no < 100 or packet.packet_no % 2 == 0:
                    action = self.get_action(packet, source_id)
                    last_jump_time = packet.current_timestamp
                    packet.current_timestamp = self.env.now
                    self.send(action, packet)
                    if last_jump_time is not None:
                        reward = self.env.now - last_jump_time + self.q_routing_table[packet.dest_host_id][action]
                        info_packet = InformationPacket(packet.dest_host_id, packet.packet_no, reward, packet.flow_id)
                        self.send(source_id, info_packet)
                else:
                    action = self.get_action(packet, source_id)
                    self.send(action, packet)
            elif self.algorithm == 'ant':
                next_port = self.data_ant_select_port(packet.dest_host_id, source_id)
                self.send(next_port, packet)
            elif self.algorithm == 'dqn':
                if self.model_local == None:
                    self.generate_neural_network_agent()
                state = self.collect_state_information(packet, source_id)
                (action_num, action_list, hidden_state0, hidden_state1) = self.get_action_dqn(state)
                #print(action_num, action_list, hidden_state)
                q_value = action_list[action_num]
                action = self.actions[action_num]
                key = (packet.flow_id, packet.packet_no)
                self.saved_state_action[key] = [state, action_num, hidden_state0, hidden_state1]
                last_jump_time = packet.current_timestamp
                packet.current_timestamp = self.env.now
                self.send(action, packet)
                if last_jump_time is not None:
                    reward = (last_jump_time - self.env.now) + q_value
                    #if self.node_id == 'N2A' and packet.packet_no % 100 == 0:
                      #print(reward, packet.packet_no)
                    info_packet = InformationPacket(packet.dest_host_id, packet.packet_no, reward, packet.flow_id)
                    self.send(source_id, info_packet)

        elif packet.head == 'a':
            if self.algorithm == 'dijkstra':
                self.send(self.search_next_jump_backward(packet.dest_host_id), packet)
            elif self.algorithm == 'q':
                if packet.dest_host_id in list(self.adj_ues.keys()):
                    action = self.adj_ues[packet.dest_host_id]
                    reward_value = 0
                else:
                    action = self.get_action(packet, source_id)
                    reward_value = self.q_routing_table[packet.dest_node_id][action]
                packet.current_timestamp = self.env.now
                self.send(action, packet)
                if packet.current_timestamp is not None:
                    reward = self.env.now - packet.current_timestamp + reward_value
                    info_packet = InformationPacket(packet.dest_node_id, packet.packet_no, reward, packet.flow_id)
                    self.send(source_id, info_packet)
            elif self.algorithm == 'ant':
                if packet.dest_host_id in list(self.adj_ues.keys()):
                    next_port = self.adj_ues[packet.dest_host_id]
                else:
                    next_port = self.data_ant_select_port(packet.dest_node_id, source_id)
                self.send(next_port, packet)

        elif packet.head == 'i':
            if self.algorithm == 'q':
                self.updating_q_routing_table(packet, source_id)
            elif self.algorithm == 'dqn':
                reward = packet.reward
                state_action = self.saved_state_action[(packet.flow_id, packet.id)]
                state = state_action[0]
                action = state_action[1]
                hidden_state0 = state_action[2]
                hidden_state1 = state_action[3]
                #print(hidden_state)
                done = packet.done
                next_state = self.collect_state_information(packet, source_id)
                self.step(state, action, reward, next_state, hidden_state0, hidden_state1, done)

        elif packet.head == 'f':
            packet.visited.append(self.node_id)
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
                else:
                    packet.stack_list.append(self.node_id)
                    if self.node_id in packet.stack:
                        print('ERROR: Cycle Detected')
                    packet.stack[self.node_id] = self.env.now
                next_port = self.ant_select_port(packet, source_id)

                if next_port is not None:
                    self.send(next_port, packet)

        elif packet.head == 'b':
            self.update_the_trip_list(packet)
            self.update_the_pheromones(packet, source_id)
            # if self.node_id == 'N3A':
            # print('Map improved at',self.env.now, packet.packet_no)
            if packet.dest_host_id == self.node_id:
                # print('EVENT:', self.node_id, 'receives its backforward ant #', packet.packet_no,'with tag of', packet.tag)
                pass
            else:
                next_port = packet.path.pop()
                self.send(next_port, packet)

        elif packet.head == 'l':
            pos = self.iab_id_list.index(packet.node_id)
            self.neighbor_info[pos] = packet.level
            if packet.node_id not in list(self.adj_iab.keys()):
                self.adj_iab[packet.node_id] = source_id

    def search_next_jump_forward(self, dest_id):
        if dest_id in self.forwardspaceket:
            return self.forwardspaceket[dest_id][0]
        else:
            raise Exception("ERROR: Can not find forwarding path", self.node_id)
            return None

    def search_next_jump_backward(self, dest_id):
        if dest_id in self.backwardspacket:
            return self.backwardspacket[dest_id][0]
        else:
            raise Exception("ERROR: Can not find forwarding path", self.node_id)
            return None

    def send(self, port, packet):
        self.env.process(self.add_packets(port, packet))

    def send_direct(self, port, packet):
        self.adj_ports[port].receive(packet, self.node_id)

    def sending_out_packets(self):
        while True:
            yield self.node_usage[1].get(1)
            port_n_packet = self.packet_queue.popleft()
            yield self.env.timeout(1 / 1.0E6)
            yield self.node_usage[0].get(1)
            self.env.process(self.delay_fun(port_n_packet[0], port_n_packet[1]))

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def send_to_all_expect_direct(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send_direct(ports, packet)

    def start_ant_colony_algorithm(self):
        # print('EVENT: IAB Node',self.node_id ,"Start ACO Routing at", self.env.now, self.adj_ports)
        nk = float(len(self.adj_ports))
        self.threshold = 1 / (nk * 5)
        for iab_id in self.iab_id_list:
            if self.node_id != iab_id:
                orig_dict_pheromones = {}
                for ports in list(self.adj_ports.keys()):
                    orig_dict_pheromones[ports] = 1.0 / nk
                self.pheromones_table[iab_id] = orig_dict_pheromones
        tag = 0
        while True:
            id = 0
            while id < self.ants_num:
                dest_host_id = np.random.choice(self.iab_id_list, 1)
                if dest_host_id[0] != self.node_id:
                    forward_ant_packet = ForwardAnt(self.node_id, dest_host_id[0], id, tag)
                    forward_ant_packet.stack[self.node_id] = self.env.now
                    forward_ant_packet.stack_list.append(self.node_id)
                    forward_ant_packet.visited.append(self.node_id)
                    next_port_id = np.random.choice(list(self.pheromones_table[dest_host_id[0]].keys()), 1)
                    self.send(next_port_id[0], forward_ant_packet)
                    id += 1
            yield self.env.timeout(5)
            tag += 1

    def start_radar_routing(self):
        print("EVENT: IAB Node", self.node_id, "Start Radar Routing at", self.env.now)
        tag = 0
        while True:
            packet = RadarPacket(self.node_id, tag)
            self.send_to_all_expect(packet)
            yield self.env.timeout(5)
            tag += 1

    def update_the_pheromones(self, packet, source_id):
        dest_pheromones_table = copy.deepcopy(self.pheromones_table[packet.src_host_id])
        prob = dest_pheromones_table[source_id]
        time_gap = self.env.now - packet.stack[self.node_id]
        dimensionless_measure = time_gap / (self.c * self.trip[0])
        if dimensionless_measure >= 1:
            dimensionless_measure = 1
        new_p = prob + (1 - dimensionless_measure) * (1 - prob)
        for key in list(dest_pheromones_table.keys()):
            res = dest_pheromones_table[key] - (1 - dimensionless_measure) * dest_pheromones_table[key]
            # if res < self.threshold:
            #    res = 0.0
            dest_pheromones_table[key] = res
        dest_pheromones_table[source_id] = new_p
        self.pheromones_table[packet.src_host_id] = copy.deepcopy(dest_pheromones_table)
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
        reward = packet.reward
        current_q = self.q_routing_table[packet.dest_host_id][source_id]
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_routing_table[packet.dest_host_id][source_id] = new_q

    ### Functions for DQN
    def generate_neural_network_agent(self):
        print('EVENT:', self.node_id, 'is currently generating neural network')
        num_dest = len(self.iab_id_list)
        self.actions = list(self.adj_iab.values()) + list(self.adj_donors.values())
        self.action_size = len(self.actions)
        model1 = INPUT_NN(num_dest, self.output_size)
        model2 = INPUT_NN(self.num_actions_hist * num_dest, self.output_size)
        model3 = INPUT_NN(self.num_future_dest * num_dest, self.output_size)
        model4 = INPUT_NN(num_dest, self.output_size)
        self.model_local = DQN(self.input_size, self.hidden_size, self.action_size, model1, model2, model3, model4).to(
            self.device)
        self.optimizer = optim.SGD(self.model_local.parameters(), lr=0.2)
        self.memory = ReplayBuffer(self.action_size, self.bufffer_size, self.batch_size)
        self.actions_hist = [[0 for i in range(num_dest)] for j in range(self.num_actions_hist)]
        self.neighbor_info = [0 for i in range(num_dest)]
        self.hidden0 = Variable(torch.zeros(1, 1, self.hidden_size).float())
        self.hidden1 = Variable(torch.zeros(1, 1, self.hidden_size).float())

    def step(self, state, action, reward, next_step, hidden_state0, hidden_state1, done):  # Learning process for every step
        #print(hidden_state)
        self.memory.add(state, action, reward, hidden_state0, hidden_state1, next_step, done)
        if len(self.memory) > self.batch_size:
            experience = self.memory.sample()
            self.learn(experience, 0.9)

    def learn(self, experiences, gamma):
        state0, state1, state2, state3, actions, rewards, hidden_state0, hidden_state1, next_state0, next_state1, next_state2, next_state3, done = experiences
        loss_fn = torch.nn.MSELoss()
        self.model_local.train()
        predicted_targets, hidden = self.model_local(state0, state1, state2, state3, hidden_state0, hidden_state1)
        predicted_targets = predicted_targets.gather(1, actions)

        labels = rewards
        loss = loss_fn(predicted_targets, labels).to(self.device)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    def collect_state_information(self, packet, source_id):
        destion = packet.dest_host_id
        pos = self.iab_id_list.index(destion)
        destion_list = np.array([0 for i in range(len(self.iab_id_list))])
        destion_list[pos] = 1
        action_list = np.array(self.actions_hist)
        action_list = action_list.flatten()
        ## need to modify - Brooklyn
        future_dest_list = np.array([destion_list for i in range(self.num_future_dest)])
        future_dest_list = future_dest_list.flatten()
        neighbor_info_list = np.array(self.neighbor_info)
        state = [destion_list, action_list, future_dest_list, neighbor_info_list]
        for i in range(len(state)):
            state[i] = torch.from_numpy(state[i]).float().unsqueeze(0).to(self.device)
        return state

    def get_action_dqn(self, state):
        #state = torch.from_numpy(state).float().unsqueeze(0).to(self.device)
        self.model_local.eval()
        with torch.no_grad():
            action_values, (h1, c1) = self.model_local(state[0], state[1], state[2], state[3], self.hidden0, self.hidden1)
            self.hidden0 = h1
            self.hidden1 = c1
        if random.random() > self.epsilon:
            return (np.argmax(action_values.cpu().data.numpy()), action_values.cpu().data.numpy()[0], self.hidden0, self.hidden1)
        else:
            return (random.choice(np.arange(self.action_size)), action_values.cpu().data.numpy()[0], self.hidden0, self.hidden1)

