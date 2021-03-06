import simpy
from packet import RadarPacket, ForwardAnt, BackwardAnt, InformationPacket, \
    level_packet, HelloPacketI, RREQ, Broadcast, RREP
from dqn_model import INPUT_NN, DQN, ReplayBuffer
import collections
import torch
import torch.optim as optim
import numpy as np
import random
import copy
from torch.autograd import Variable

class IAB_Node(object):
    def __init__(self, env, node_id, algorithm, legacy, filename):
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
        self.legacy = legacy
        self.filename = filename
        self.session_tag_table = {}

        if self.algorithm == 'dijkstra':
            self.radar_tag_table = {}
            self.echo_tag_table = {}
            self.backwardspacket = {}
            self.forwardspaceket = {}
            # self.env.process(self.start_radar_routing())

        if self.algorithm == 'q':
            self.q_routing_table = {}
            self.learning_rate = 0.1
            self.epsilon = 0.1
            self.penalty = -10

        if self.algorithm == 'ant':
            self.threshold = float(0.0)
            self.iteration = 10
            self.ants_num = 200
            self.pheromones_table = {}  # Routing Table, it has the probabilities P(i,n) which express the goodness
            # of choosing n as next node when the destination is i, current, it only have one destination - iab donor
            # self.andict_t_pheromones = {}
            self.trip = [0.0, 0.0, []]  # estimates of mean values and variances from node k to iab donor
            self.c = 2

        if self.algorithm == 'dqn':
            self.bufffer_size = int(1e3)
            self.batch_size = 64
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
            self.actions_hist = collections.deque(maxlen=self.num_actions_hist)
            self.neighbor_info = []
            self.packet_queue_dest = collections.deque()
            self.saved_state_action = {}
            self.penalty = -10
            self.adj_link_egree_level = {}
            self.model_local = None
            self.action_size = None
            self.optimizer = None
            self.memory = None
            self.hidden0 = None
            self.hidden1 = None

        elif self.algorithm == 'hpso' or self.algorithm == 'genetic':
            self.table = {}
            self.rreq_pool = {}
            self.population = 1
            self.percentage_m = 0.6
            self.best_path = {}
            self.rreq_num = 200
            self.table = {}

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
            flag = False
            for i in norm_prob:
                if np.isnan(i):
                    flag = True
            if not flag:
                norm_prob = [1.0 / len(ports_id_list)] * len(ports_id_list)
                for i in list(dest_pheromones_table.keys()):
                    self.pheromones_table[ant_packet.dest_host_id][i] = 1.0 / len(ports_id_list)
            next_port_id_list = np.random.choice(ports_id_list, 1, p=norm_prob)
            next_port_id = next_port_id_list[0]
            if next_port_id not in ant_packet.visited:
                return next_port_id
            else:
                next_port_id_list = np.random.choice(ports_id_list, 1)
                next_port_id = next_port_id_list[0]
                return next_port_id

    def collect_state_information(self, packet, source_id):
        if packet.head == 'd':
            destination = packet.dest_node_id
        else:
            destination = packet.dest_host_id
        pos = self.iab_id_list.index(destination)
        destination_list = np.array([0 for i in range(len(self.iab_id_list))])
        destination_list[pos] = 1
        action_list = np.array(self.actions_hist)
        egree_link_state = np.array(list(self.adj_link_egree_level.values()))
        neighbor_info_list = np.array(self.neighbor_info)
        state = [destination_list, action_list, egree_link_state, neighbor_info_list]
        for i in range(len(state)):
            state[i] = torch.from_numpy(state[i]).float().unsqueeze(0).to(self.device)
        return state

    def crossover(self, stack1, stack2):
        stack1nodes = list(stack1.keys())
        stack2nodes = list(stack2.keys())
        common_nodes = [x for x in stack1nodes if x in stack2nodes]
        results = []
        for node in common_nodes:
            if node != self.node_id and node != stack1nodes[0]:
                pos1 = stack1nodes.index(node)
                pos2 = stack2nodes.index(node)
                time11 = stack1[node] - stack1[stack1nodes[0]]
                time12 = stack1[self.node_id] - stack1[node]
                time21 = stack2[node] - stack2[stack2nodes[0]]
                time22 = stack2[self.node_id] - stack2[node]
                newpath1 = stack1nodes[:pos1+1] + stack2nodes[pos2+1:]
                newtime1 = time11 + time22
                newpath2 = stack2nodes[:pos2] + stack1nodes[pos1:]
                newtime2 = time21 + time12
                if newtime1 > newtime2:
                    results.append((newpath2, newtime2))
                else:
                    results.append((newpath1, newtime1))
        if not results:
            return ([], 0)
        else:
            sortedresult = sorted(results, key=lambda x: x[1], reverse=False)
            return sortedresult[0]

    def crossover_process(self, left_population, packet_dict):
        stack_pool = []
        for item in left_population:
            packet_id = item[0]
            packet = packet_dict[packet_id]
            stack_pool.append(packet.stack)
        result = []
        for i in range(len(stack_pool)-1):
            for j in range(i+1, len(stack_pool)):
                (path, time) = self.crossover(stack_pool[i], stack_pool[j])
                if path != []:
                    if (path, time) not in result:
                        result.append((path, time))
        return result

    def data_ant_select_port(self, dest_id, source_id):
        dest_pheromones_table = copy.deepcopy(self.pheromones_table[dest_id])
        if source_id in dest_pheromones_table:
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
        yield self.env.timeout(0.1)
        num_dest = len(self.iab_id_list)
        self.neighbor_info = [0 for i in range(num_dest)]
        while True:
            yield self.env.timeout(0.005)
            level = sum(list(self.adj_link_egree_level.values()))
            packet = level_packet(self.node_id, level)
            self.send_to_all_expect_direct(packet)

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

    def generate_neural_network_agent(self):
        print('EVENT:', self.node_id, 'is currently generating neural network')
        if self.legacy == 'n':
            num_dest = len(self.iab_id_list)
            self.actions = list(self.adj_iab.values()) + list(self.adj_donors.values())
            self.action_size = len(self.actions)
            model1 = INPUT_NN(num_dest, self.output_size)
            model2 = INPUT_NN(self.num_actions_hist, self.output_size)
            model3 = INPUT_NN(self.action_size, self.output_size)
            model4 = INPUT_NN(num_dest, self.output_size)
            self.model_local = DQN(self.input_size, self.hidden_size, self.action_size, model1, model2, model3,
                                   model4).to(
                self.device)
            self.optimizer = optim.Adagrad(self.model_local.parameters(), lr=0.02)
            self.memory = ReplayBuffer(self.action_size, self.bufffer_size, self.batch_size)
            for j in range(self.num_actions_hist):
                self.actions_hist.append(0)
            self.hidden0 = Variable(torch.zeros(1, 1, self.hidden_size).float())
            self.hidden1 = Variable(torch.zeros(1, 1, self.hidden_size).float())
        else:
            num_dest = len(self.iab_id_list)
            self.actions = list(self.adj_iab.values()) + list(self.adj_donors.values())
            self.action_size = len(self.actions)
            model1 = INPUT_NN(num_dest, self.output_size)
            model2 = INPUT_NN(self.num_actions_hist, self.output_size)
            model3 = INPUT_NN(self.action_size, self.output_size)
            model4 = INPUT_NN(num_dest, self.output_size)
            self.model_local = DQN(self.input_size, self.hidden_size, self.action_size, model1, model2, model3,
                                   model4).to(
                self.device)
            self.optimizer = optim.Adagrad(self.model_local.parameters(), lr=0.02)
            self.memory = ReplayBuffer(self.action_size, self.bufffer_size, self.batch_size)
            for j in range(self.num_actions_hist):
                self.actions_hist.append(0)
            self.hidden0 = Variable(torch.zeros(1, 1, self.hidden_size).float())
            self.hidden1 = Variable(torch.zeros(1, 1, self.hidden_size).float())
            filename = self.node_id + ".pth"
            checkpoint = torch.load(filename)
            self.model_local.load_state_dict(checkpoint['net'])
            self.optimizer.load_state_dict(checkpoint['opt'])

    def genetic_algorithm(self, order_list, packet_dict):
        if self.algorithm == 'genetic':
            num_population = round(self.population * len(order_list))
        else:
            num_population = len(order_list)
        population = order_list[:num_population]
        m_percent = round(self.percentage_m * num_population)
        left_size = num_population - m_percent
        path_fitness = []
        for i in range(m_percent):
            packet = packet_dict[order_list[i][0]]
            path_fitness.append((packet.path, order_list[i][1]))
        paths = self.crossover_process(population[m_percent:], packet_dict)
        result = path_fitness
        result += paths
        return result[:num_population]

    def get_action(self, packet, source_id):
        if packet.direction == 'up':
            state = packet.dest_host_id
        elif packet.direction == 'down':
            state = packet.dest_node_id
        if state not in self.q_routing_table:
            self.generate_q_routing_table(state, packet, source_id)
        random_num = np.random.rand()
        if random_num > self.epsilon:
            action = min(self.q_routing_table[state], key=self.q_routing_table[state].get)
        else:
            action = np.random.choice(list(self.q_routing_table[state]))
        return action

    def get_action_dqn(self, state):
        self.model_local.eval()
        with torch.no_grad():
            action_values, (h1, c1) = self.model_local(state[0], state[1], state[2], state[3], self.hidden0,
                                                       self.hidden1)
            self.hidden0 = h1
            self.hidden1 = c1
        if random.random() > self.epsilon:
            return (np.argmax(action_values.cpu().data.numpy()), action_values.cpu().data.numpy()[0], self.hidden0,
                    self.hidden1)
        else:
            return (
                random.choice(np.arange(self.action_size)), action_values.cpu().data.numpy()[0], self.hidden0,
                self.hidden1)

    def hello_packet(self):
        while True:
            packet = HelloPacketI(self.node_id, self.env.now)
            self.send_to_all_expect_direct(packet)
            yield self.env.timeout(5)

    def h_particle_swarm_opt(self, trigger_packet):
        key = (trigger_packet.source_id, trigger_packet.tag)
        path_list = self.rreq_pool[key][:10]
        if key not in self.best_path:
            self.best_path[key] = path_list[0]
        time_dict = {}
        packet_dict = {}
        for i in range(len(path_list)):
            packet = path_list[i]
            source_id = packet.source_id
            total_t = packet.stack[self.node_id] - packet.stack[source_id]
            time_dict[i] = total_t
            packet_dict[i] = packet
        time_dict_order = sorted(time_dict.items(), key=lambda x: x[1], reverse=False)
        possible_paths = self.genetic_algorithm(time_dict_order, packet_dict)
        time_table = self.time_to_prob(possible_paths)
        returnpath = trigger_packet.path[:-1]
        next_node = returnpath.pop(-1)
        rrep_packet = RREP(self.node_id, packet.source_id, time_table, packet.tag, returnpath)
        next_port = self.adj_iab[next_node]
        self.send(next_port, rrep_packet)

    def initialize(self):
        if self.algorithm == 'ant':
            self.env.process(self.hello_packet())
            self.env.process(self.start_ant_colony_algorithm())
        elif self.algorithm == 'dqn':
            self.env.process(self.hello_packet())
            self.env.process(self.exchange_info())
        elif self.algorithm == 'genetic':
            self.env.process(self.hello_packet())
            self.env.process(self.start_rreq_route_discovery())
        elif self.algorithm == 'hpso':
            self.env.process(self.hello_packet())
            self.env.process(self.start_rreq_route_discovery_pso())

    def learn(self, experiences):
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

    def normalization(self, dest_id):
        dest_pheromones_table = copy.deepcopy(self.pheromones_table[dest_id])
        keys = list(dest_pheromones_table.keys())
        values = dest_pheromones_table.values()
        norm = [float(i) / sum(values) for i in values]
        for i in range(len(keys)):
            dest_pheromones_table[keys[i]] = norm[i]
        self.pheromones_table[dest_id] = copy.deepcopy(dest_pheromones_table)

    def receive(self, packet, source_id):
        if packet.head == 'csr':
            if packet.src_node_id is None:
                packet.src_node_id = self.node_id
            src_host_id = packet.src_host_id
            router_tag_table = self.session_tag_table
            tag = packet.tag
            if src_host_id not in router_tag_table or router_tag_table[src_host_id] < tag:
                router_tag_table[src_host_id] = tag
                self.send_to_all_expect(packet, source_id)

        elif packet.head == 'h':
            if packet.ue_id not in list(self.adj_ues.keys()):
                self.adj_ues[packet.ue_id] = source_id

        elif packet.head == 'h-i':
            if packet.iab_id not in list(self.adj_iab.keys()):
                self.adj_iab[packet.iab_id] = source_id

        elif packet.head == 'h-d':
            if packet.donor_id not in list(self.adj_donors.keys()):
                self.adj_donors[packet.donor_id] = source_id

        elif packet.head == 'l':
            pos = self.iab_id_list.index(packet.node_id)
            self.neighbor_info[pos] = packet.level
            if packet.jump < 5:
                packet.jump += 1
                self.send_to_all_expect_direct(packet, source_id)

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
                src_host_id = packet.src_host_id
                key = (dest_host_id, src_host_id)
                router_tag_table = self.echo_tag_table
                tag = packet.tag
                if key not in router_tag_table or router_tag_table[key] < tag:
                    self.forwardspaceket[key] = (source_id, tag)
                    packet.add_path(self.node_id)
                    self.send(self.backwardspacket[dest_host_id][0], packet)

        elif packet.head == 'd':
            if packet.src_node_id == None:
                packet.src_node_id = self.node_id
            if self.algorithm == 'dijkstra':
                self.send(self.search_next_jump_forward((packet.src_host_id, packet.dest_host_id)), packet)
            elif self.algorithm == 'genetic' or self.algorithm == 'hpso':
                if packet.src_node_id == self.node_id:
                    dest = packet.dest_node_id
                    if dest not in list(self.table.keys()):
                        print(self.node_id, self.table)
                    table = self.table[dest]
                    if table == []:
                        print("ERROR Table")
                    route_list = [route for route, prob in table]
                    prob_list = [prob for route, prob in table]
                    if len(prob_list) == 1:
                        selected_route = route_list[0]
                    else:
                        if prob_list == [] or route_list == []:
                            print("ERROR")
                        selected_route_list = np.random.choice(route_list, 1, p=prob_list)
                        selected_route = selected_route_list[0]
                    next_node = selected_route[1]
                    if next_node in list(self.adj_iab.keys()):
                        packet.route = selected_route[2:]
                        next_port = self.adj_iab[next_node]
                    else:
                        packet.route = []
                        next_port = self.adj_donors[next_node]
                    self.send(next_port, packet)
                elif packet.dest_host_id in list(self.adj_ues.keys()):
                        action = self.adj_ues[packet.dest_host_id]
                        self.send(action, packet)
                else:
                    route = packet.route
                    next_node = route[0]
                    if next_node in list(self.adj_iab.keys()):
                        packet.route = route[1:]
                        next_port = self.adj_iab[next_node]
                    else:
                        packet.route = []
                        next_port = self.adj_donors[next_node]
                    self.send(next_port, packet)

            elif self.algorithm == 'q':
                if packet.direction == 'up':
                    action = self.get_action(packet, source_id)
                    last_jump_time = packet.current_timestamp
                    packet.current_timestamp = self.env.now
                    self.send(action, packet)
                    if last_jump_time is not None:
                        reward = self.env.now - last_jump_time + self.q_routing_table[packet.dest_host_id][action]
                        info_packet = InformationPacket(packet.dest_host_id, packet.packet_no, reward, packet.flow_id)
                        self.send(source_id, info_packet)
                else:
                    if packet.dest_host_id in list(self.adj_ues.keys()):
                        action = self.adj_ues[packet.dest_host_id]
                        self.send(action, packet)
                        last_jump_time = packet.current_timestamp
                        reward = self.env.now - last_jump_time
                        info_packet = InformationPacket(packet.dest_node_id, packet.packet_no, reward, packet.flow_id)
                        self.send(source_id, info_packet)
                    else:
                        action = self.get_action(packet, source_id)
                        last_jump_time = packet.current_timestamp
                        packet.current_timestamp = self.env.now
                        self.send(action, packet)
                        if last_jump_time is not None:
                            reward = self.env.now - last_jump_time + self.q_routing_table[packet.dest_node_id][action]
                            info_packet = InformationPacket(packet.dest_node_id, packet.packet_no, reward,
                                                            packet.flow_id)
                            self.send(source_id, info_packet)

            elif self.algorithm == 'ant':
                if self.node_id== 'ND1' and packet.dest_host_id == 'D1':
                    action = self.adj_donors[packet.dest_host_id]
                    self.send(action, packet)
                else:
                    if packet.dest_host_id in list(self.adj_ues.keys()):
                        action = self.adj_ues[packet.dest_host_id]
                        self.send(action, packet)
                    else:
                        next_port = self.data_ant_select_port(packet.dest_node_id, source_id)
                        self.send(next_port, packet)

            elif self.algorithm == 'dqn':
                if packet.direction == 'up':
                    if self.model_local == None:
                        self.generate_neural_network_agent()
                    state = self.collect_state_information(packet, source_id)
                    (action_num, action_list, hidden_state0, hidden_state1) = self.get_action_dqn(state)
                    self.actions_hist.append(action_num)
                    q_value = action_list[action_num]
                    action = self.actions[action_num]
                    key = (packet.flow_id, packet.packet_no)
                    self.saved_state_action[key] = [state, action_num, hidden_state0, hidden_state1]
                    last_jump_time = packet.current_timestamp
                    packet.current_timestamp = self.env.now
                    self.send(action, packet)
                    if last_jump_time is not None:
                        reward = (last_jump_time - self.env.now) + q_value
                        info_packet = InformationPacket(packet.dest_host_id, packet.packet_no, reward, packet.flow_id)
                        self.send(source_id, info_packet)
                else:
                    if packet.dest_host_id in list(self.adj_ues.keys()):
                        action = self.adj_ues[packet.dest_host_id]
                        self.send(action, packet)
                        last_jump_time = packet.current_timestamp
                        reward = (last_jump_time - self.env.now)
                        info_packet = InformationPacket(packet.dest_node_id, packet.packet_no, reward, packet.flow_id, 1)
                        self.send(source_id, info_packet)
                    else:
                        if self.model_local == None:
                            self.generate_neural_network_agent()
                        state = self.collect_state_information(packet, source_id)
                        (action_num, action_list, hidden_state0, hidden_state1) = self.get_action_dqn(state)
                        self.actions_hist.append(action_num)
                        q_value = action_list[action_num]
                        action = self.actions[action_num]
                        key = (packet.flow_id, packet.packet_no)
                        self.saved_state_action[key] = [state, action_num, hidden_state0, hidden_state1]
                        last_jump_time = packet.current_timestamp
                        packet.current_timestamp = self.env.now
                        self.send(action, packet)
                        if last_jump_time is not None:
                            reward = (last_jump_time - self.env.now) + q_value
                            info_packet = InformationPacket(packet.dest_node_id, packet.packet_no, reward,
                                                            packet.flow_id)
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
                # print(hidden_state)
                done = packet.done
                next_state = self.collect_state_information(packet, source_id)
                self.step(state, action, reward, next_state, hidden_state0, hidden_state1, done)

        elif packet.head == 'p':
            # print("WARNING: Data Packet",packet.id, "of flow id", packet.flow_id, "is lost")
            if self.algorithm == 'dqn':
                reward = self.penalty
                state_action = self.saved_state_action[(packet.flow_id, packet.id)]
                state = state_action[0]
                action = state_action[1]
                hidden_state0 = state_action[2]
                hidden_state1 = state_action[3]
                # print(hidden_state)
                done = 0
                next_state = self.collect_state_information(packet, source_id)
                self.step(state, action, reward, next_state, hidden_state0, hidden_state1, done)
            #elif self.algorithm == 'q':
                #self.updating_q_routing_table_penalty(packet, source_id)

        elif packet.head == 'f':
            jump = packet.max_jump
            if jump == 0:
                pass
            else:
                if packet.dest_host_id == self.node_id:
                    foward_path = packet.stack_list
                    next_port = foward_path.pop()
                    stack = packet.stack
                    stack[self.node_id] = self.env.now
                    backward_ant = BackwardAnt(self.node_id, packet.src_host_id, foward_path, stack, packet.packet_no,
                                           packet.tag, self.env.now)
                    self.send(next_port, backward_ant)
                else:
                    packet.visited.append(self.node_id)
                    if self.node_id in packet.stack_list:
                        loc = packet.stack_list.index(self.node_id)
                        pop_list = packet.stack_list[(loc + 1):]
                        for e in pop_list:
                            if e in list(packet.stack.keys()):
                                del packet.stack[e]
                        packet.stack_list = packet.stack_list[:loc + 1]
                    else:
                        packet.stack_list.append(self.node_id)
                        packet.stack[self.node_id] = self.env.now
                    jump -= 1
                    packet.max_jump -= jump
                    if self.node_id == 'ND1' and packet.dest_host_id == 'D1':
                        action = self.adj_donors[packet.dest_host_id]
                        self.send(action, packet)
                    else:
                        next_port = self.ant_select_port(packet, source_id)
                        if next_port is not None:
                            self.send(next_port, packet)

        elif packet.head == 'b':
            if packet.src_host_id[0] == 'D' and self.node_id == 'ND1':
                pass
            else:
                self.update_the_trip_list(packet)
                self.update_the_pheromones(packet, source_id)
            if packet.dest_host_id == self.node_id:
                #if packet.dest_host_id == 'N3A':
                    #print('receive the backwardant', packet.packet_no, self.env.now)
                pass
            else:
                next_port = packet.path.pop()
                self.send(next_port, packet)

        elif packet.head == 'U':
            if self.algorithm == 'dqn':
                level = packet.level
                self.adj_link_egree_level[packet.id] = float(level)

        elif packet.head == 'RREQ':
            if packet.dest_id == self.node_id:
                packet.stack[self.node_id] = self.env.now
                packet.path.append(self.node_id)
                key = (packet.source_id, packet.tag)
                if key not in list(self.rreq_pool.keys()):
                    self.rreq_pool[key] = []
                    self.rreq_pool[key].append(packet)
                    self.env.process(self.rreq_destination_process(packet))
                else:
                    if packet not in self.rreq_pool[key]:
                        self.rreq_pool[key].append(packet)
            else:
                if self.algorithm == 'genetic':
                    packet.stack[self.node_id] = self.env.now
                    packet.path.append(self.node_id)
                    if packet.dest_id == self.node_id:
                        pass  # Brooklyn implement later
                    else:
                        visited_node = packet.path
                        adj_iab = list(self.adj_iab.keys()) + list(self.adj_donors.keys())
                        avaliable_node = []
                        for iab in adj_iab:
                            if iab not in visited_node:
                                avaliable_node.append(iab)
                        if avaliable_node != []:
                            next_node = np.random.choice(avaliable_node, 1)
                            if next_node in list(self.adj_iab.keys()):
                                next_port = self.adj_iab[next_node[0]]
                            else:
                                next_port = self.adj_donors[next_node[0]]
                            self.send(next_port, packet)
        if packet.head == 'broad':
            if packet.dest_id == self.node_id:
                new_stack = packet.stack.copy()
                new_path = packet.path.copy()
                new_packet = Broadcast(packet.source_id, packet.dest_id, new_stack, new_path, packet.tag, packet.jump)
                new_packet.stack[self.node_id] = self.env.now
                new_packet.path.append(self.node_id)

                key = (new_packet.source_id, new_packet.tag)
                # print(new_packet.path, self.env.now)
                if new_packet.dest_id == self.node_id:
                    if key not in list(self.rreq_pool.keys()):
                        self.rreq_pool[key] = []
                        self.rreq_pool[key].append(new_packet)
                    else:
                        if len(self.rreq_pool[key]) < 5:
                            self.rreq_pool[key].append(new_packet)
                        elif len(self.rreq_pool[key]) == 5:
                            self.rreq_pool[key].append(new_packet)
                            self.h_particle_swarm_opt(new_packet)
                        else:
                            pass

            else:
                if packet.jump == 0:
                    pass
                else:
                    if self.node_id not in packet.path:
                        packet.jump -= 1
                        new_stack = packet.stack.copy()
                        new_path = packet.path.copy()
                        new_packet = Broadcast(packet.source_id, packet.dest_id, new_stack, new_path, packet.tag, packet.jump)
                        new_packet.stack[self.node_id] = self.env.now
                        new_packet.path.append(self.node_id)
                        if packet.dest_id == self.node_id:
                            print("ERROR")
                            pass  # Same as Donor
                        else:
                            self.send_to_all_expect_direct(new_packet, source_id)

        elif packet.head == 'RREP':

            if packet.dest_id == self.node_id:
                self.table[packet.source_id] = packet.time_table
            else:
                next_node = packet.path.pop(-1)
                next_port = self.adj_iab[next_node]
                self.send_direct(next_port, packet)

    def rreq_destination_process(self, first_packet):
        yield self.env.timeout(2)
        key = (first_packet.source_id, first_packet.tag)
        time_dict = {}
        packet_dict = {}
        for packet in self.rreq_pool[key]:
            source_id = packet.source_id
            total_t = packet.stack[self.node_id] - packet.stack[source_id]
            time_dict[packet.id] = total_t
            packet_dict[packet.id] = packet
        time_dict_order = sorted(time_dict.items(), key=lambda x: x[1], reverse=False)
        possible_paths = self.genetic_algorithm(time_dict_order, packet_dict)
        if possible_paths == []:
          print("ERROR possible path is",time_dict_order, possible_paths, self.rreq_pool[key],first_packet.source_id)
        time_table = self.time_to_prob(possible_paths)
        returnpath = first_packet.path[:-1]
        next_node = returnpath.pop(-1)
        rrep_packet = RREP(self.node_id, packet.source_id, time_table, packet.tag, returnpath)
        next_port = self.adj_iab[next_node]
        self.send(next_port, rrep_packet)

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
        yield self.env.timeout(0.1)
        # print('EVENT: IAB Node',self.node_id ,"Start ACO Routing at", self.env.now, self.adj_ports)
        nk = float(len(self.adj_iab) + len(self.adj_donors))
        test_list = list(self.adj_iab.values()) + list(self.adj_donors.values())
        self.threshold = 1 / (nk * 5)
        for iab_id in self.iab_id_list:
            if self.node_id != iab_id:
                orig_dict_pheromones = {}
                for ports in test_list:
                    orig_dict_pheromones[ports] = 1.0 / nk
                self.pheromones_table[iab_id] = orig_dict_pheromones
        tag = 0
        while True:
            id = 0
            while id < self.ants_num:
                dest_host_id = ['D1']#np.random.choice(self.iab_id_list, 1)
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

    def start_rreq_route_discovery(self):
        yield self.env.timeout(0.1)
        tag = 0
        while True:
            for dest in self.iab_id_list:
                if dest != self.node_id:
                    id = 0
                    while id < 200:
                        rreq_packet = RREQ(id, self.node_id, dest, self.env.now, tag)
                        next_port_id = np.random.choice(list(self.adj_iab.values()), 1)
                        self.send(next_port_id[0], rreq_packet)
                        id += 1
            yield self.env.timeout(3)
            tag += 1

    def start_rreq_route_discovery_pso(self):
        yield self.env.timeout(0.1)
        tag = 0
        while True:
            for dest in self.iab_id_list:
                if dest != self.node_id:
                    broadcast_packet = Broadcast(self.node_id, dest, {}, [], tag, 9)
                    broadcast_packet.stack[self.node_id] = self.env.now
                    broadcast_packet.path.append(self.node_id)
                    self.send_to_all_expect_direct(broadcast_packet)
            yield self.env.timeout(3)
            tag += 1

    def start_radar_routing(self):
        print("EVENT: IAB Node", self.node_id, "Start Radar Routing at", self.env.now)
        tag = 0
        while True:
            packet = RadarPacket(self.node_id, tag)
            self.send_to_all_expect(packet)
            yield self.env.timeout(5)
            tag += 1

    def step(self, state, action, reward, next_step, hidden_state0, hidden_state1,
             done):
        self.memory.add(state, action, reward, hidden_state0, hidden_state1, next_step, done)
        if len(self.memory) > self.batch_size:
            experience = self.memory.sample()
            self.learn(experience)

    def time_to_prob(self, paths):
        visited_path = []
        unique_path = []
        for path, time in paths:
            if path not in visited_path:
                unique_path.append((path, time))
                visited_path.append(path)
        sorted_path = sorted(unique_path, key=lambda x: x[1], reverse=False)
        time_gap_list = []
        if sorted_path == []:
          print("ERROR: Sorted Path", paths)
        min_time = 1/2 * sorted_path[0][1]
        for path, time in sorted_path:
            time_gap_list.append(1/(time - min_time))
        norm_list = [float(i)/sum(time_gap_list) for i in time_gap_list]
        result = []
        for i in range(len(norm_list)):
            result.append((sorted_path[i][0], norm_list[i]))
        return result

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

    def updating_q_routing_table_penalty(self, packet, source_id):
        reward = self.penalty
        current_q = self.q_routing_table[packet.dest_host_id][source_id]
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_routing_table[packet.dest_host_id][source_id] = new_q