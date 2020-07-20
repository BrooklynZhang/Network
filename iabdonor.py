import simpy
from packet import RadarPacket, EchoPacket, DataPacket, AckPacket, BackwardAnt, ForwardAnt, InformationPacket, HelloPacketD, RREP
from collections import defaultdict

class IAB_Donor(object):

    def __init__(self, env, donor_id, algorithm):
        self.env = env
        self.donor_id = donor_id
        self.adj_ports = {}
        self.adj_iab = {}
        self.algorithm = algorithm
        self.timetable = defaultdict(int)
        self.monitor_transmission_t = {}
        self.monitor_data_act_time = {}
        self.data_packet_time = {}
        self.env.process(self.get_access_to_iab())
        if self.algorithm == 'genetic':
            self.rreq_pool = []
            self.population = 0.6
            self.percentage_m = 0.4
        # self.env.process(self.start_radar_routing())

    def add_flow(self, flow):
        self.flows[flow.flow_id] = flow
        self.env.process(self.send_data_packets(flow))

    def add_port(self, source_id, source_port):
        if source_id in self.adj_ports:
            raise Exception('ERROR: Duplicate port name')
        self.adj_ports[source_id] = source_port

    def get_access_to_iab(self):
        while True:
            packet = HelloPacketD(self.donor_id)
            self.send_to_all_expect(packet)
            yield self.env.timeout(5)

    def receive(self, packet, source_id):
        if packet.head == 'h-i':
            if packet.iab_id not in list(self.adj_iab.keys()):
                self.adj_iab[packet.iab_id] = source_id

        if packet.head == 'r':
            #print('EVENT: IAB_DONOR', self.donor_id, 'receive the data packet from', packet.src_host_id, 'at', self.env.now)
            self.send(source_id, EchoPacket(self.donor_id, packet.src_host_id, packet.tag))

        elif packet.head == 'e':
            print('EVENT: IAB_DONOR', self.donor_id, 'receives the Echo packet from', packet.dest_host_id, 'at', self.env.now)

        elif packet.head == 'd':
            time_gap = self.env.now - packet.timestamp
            if packet.flow_id in self.monitor_transmission_t:
                self.monitor_transmission_t[packet.flow_id].append((packet.packet_no, time_gap))
            else:
                self.monitor_transmission_t[packet.flow_id] = [(packet.packet_no, time_gap)]
            if packet.ack == 'y':
                if self.algorithm in ['q', 'ant', 'dijkstra']:
                    if packet.packet_no % 500 == 0:
                        print('EVENT: IAB Donor', self.donor_id,'received the data packet from', packet.src_host_id, 'with packet id of', packet.packet_no, 'The uplink travel time is',time_gap)
                self.send(source_id, AckPacket(packet.dest_host_id, packet.src_host_id, packet.src_node_id, packet.flow_id, packet.packet_no, self.env.now, 'down'))
            else:
                if packet.packet_no % 500 == 0:
                    print('EVENT: IAB Donor', self.donor_id, 'received the data packet from', packet.src_host_id,
                          'with packet id of', packet.packet_no)
            if self.algorithm == 'q' or self.algorithm == 'dqn':
                last_jump_time = packet.current_timestamp
                if last_jump_time is not None:
                    reward = self.env.now - last_jump_time
                    info_packet = InformationPacket(packet.dest_host_id, packet.packet_no, reward, packet.flow_id, 1)
                    self.send(source_id, info_packet)
        elif packet.head == 'a':
            #print('EVENT: IAB Donor', self.donor_id, "send AckPacket to",packet.dest_host_id, 'with last iab of', packet.dest_node_id)
            pass
        elif packet.head == 'f':
            if packet.dest_host_id == self.donor_id:
                # print('EVENT: IAB Node', self.donor_id, 'received a forward ant from', packet.src_host_id,'at', self.env.now)
                foward_path = packet.stack_list
                next_port = foward_path.pop()
                stack = packet.stack
                stack[self.donor_id] = self.env.now
                backward_ant = BackwardAnt(self.donor_id, packet.src_host_id, foward_path, stack, packet.packet_no, packet.tag, self.env.now)
                self.send(next_port, backward_ant)

        elif packet.head == 'RREQ':
            packet.stack[self.donor_id] = self.env.now
            packet.path.append(self.donor_id)
            if packet.dest_id == self.donor_id:
                if self.rreq_pool == []:
                    self.rreq_pool.append(packet)
                    self.env.process(self.rreq_destination_process(packet))
                else:
                    if packet not in self.rreq_pool:
                        self.rreq_pool.append(packet)
            else:
                pass

    def rreq_destination_process(self, first_packet):
        yield self.env.timeout(1)
        time_dict = {}
        packet_dict = {}
        for packet in self.rreq_pool:
            source_id = packet.source_id
            total_t = packet.stack[self.donor_id] - packet.stack[source_id]
            time_dict[packet.id] = total_t
            packet_dict[packet.id] = packet
        time_dict_order = sorted(time_dict.items(), key=lambda x: x[1], reverse=False)
        possible_paths = self.genetic_algorithm(time_dict_order, packet_dict)
        time_table = self.time_to_prob(possible_paths)
        returnpath = first_packet.path[:-1]
        next_node = returnpath.pop(-1)
        rrep_packet = RREP(self.donor_id, packet.source_id, time_table, packet.tag, returnpath)
        self.rreq_pool = []
        next_port = self.adj_iab[next_node]
        self.send(next_port, rrep_packet)

    def time_to_prob(self, paths):
        visited_path = []
        unique_path = []
        for path, time in paths:
            if path not in visited_path:
                unique_path.append((path, time))
                visited_path.append(path)
        sorted_path = sorted(unique_path, key=lambda x: x[1], reverse=False)
        time_gap_list = []
        min_time = sorted_path[0][1] - 0.001
        for path, time in sorted_path[1:]:
            time_gap_list.append(1/(time - min_time))
        norm_list = [float(i)/sum(time_gap_list) for i in time_gap_list]
        result = [(sorted_path[0][0], 1/2)]
        for i in range(len(norm_list)):
            result.append((sorted_path[i+1][0], norm_list[i]/2))
        return result

    def genetic_algorithm(self, order_list, packet_dict):
        num_population = round(self.population * len(order_list))
        population = order_list[:num_population]
        m_percent = round(self.percentage_m * num_population)
        max_transmit_time = order_list[m_percent][1]
        path_fitness = []
        for i in range(m_percent):
            packet = packet_dict[order_list[i][0]]
            path_fitness.append((packet.path, order_list[i][1]))
        paths = self.crossover_process(max_transmit_time, population[m_percent:], packet_dict)
        result = path_fitness
        result += paths
        return result

    def crossover_process(self, time_treshold, left_population, packet_dict):
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
                    if time < 1 and (path, time) not in result:
                        result.append((path, time))
        return result


    def crossover(self, stack1, stack2):
        stack1nodes = list(stack1.keys())
        stack2nodes = list(stack2.keys())
        common_nodes = [x for x in stack1nodes if x in stack2nodes]
        results = []
        for node in common_nodes:
            if node != self.donor_id and node != stack1nodes[0]:
                pos1 = stack1nodes.index(node)
                pos2 = stack2nodes.index(node)
                time11 = stack1[node] - stack1[stack1nodes[0]]
                time12 = stack1[self.donor_id] - stack1[node]
                time21 = stack2[node] - stack2[stack2nodes[0]]
                time22 = stack2[self.donor_id] - stack2[node]
                newpath1 = stack1nodes[:pos1+1] + stack2nodes[pos2+1:]
                newtime1 = time11 + time22
                newpath2 = stack2nodes[:pos2] + stack1nodes[pos1:]
                newtime2 = time21 + time12
                if newtime1 > newtime2:
                    results.append((newpath2, newtime2))
                else:
                    results.append((newpath1, newtime1))
        if results == []:
            return ([], 0)
        else:
            sortedresult = sorted(results, key=lambda x: x[1], reverse=False)
            return sortedresult[0]

    def send(self, dest_ports, packet):
        self.adj_ports[dest_ports].receive(packet, self.donor_id)

    def send_data_packets(self, flow):
        yield self.env.timeout(flow.start_s)
        print('EVENT: Adding flow to IAB Donor', self.donor_id, 'at', self.env.now)
        total_packets = flow.num_packets
        self.monitor_data_act_time[flow.flow_id] = []
        datapacket_id = 0
        time_gamp = flow.oper_time / total_packets
        while flow.num_packets >= 0:
                if datapacket_id % 500 == 0 or datapacket_id == total_packets:
                    print('EVENT: IAB DONOR',self.donor_id,"Send DataPacket", datapacket_id,'/',total_packets,'to',flow.dest_id)
                current_time = self.env.now
                packet = DataPacket(flow.src_id, flow.dest_id, flow.flow_id, datapacket_id, current_time, flow.ack) #src_host_id, dest_host_id, flow_id, packetnum, timestamp
                key = (datapacket_id, flow.flow_id)
                self.data_packet_time[key] = current_time
                self.send_to_dest(packet, flow.dest_id)
                datapacket_id += 1
                flow.num_packets -= 1
                yield self.env.timeout(time_gamp)
        if flow.ack == 'y':
            print('EVENT: All The Data Packet of Flow Id', flow.flow_id, 'Has Been Sent, It Will Have Ack Packet')
        else:
            print('EVENT: All The Data Packet of Flow Id', flow.flow_id, 'Has Been Sent, It Will Have No Ack Packet')

    def send_to_dest(self, packet, dest_id):
        if self.algorithm == 'dijkstra':
            next_jump_port = self.timetable[dest_id][0]
            self.send(next_jump_port, packet)
        elif self.algorithm in ['q', 'ant']:
            self.send_to_all_expect(packet)

    def send_to_all_expect(self, packet, except_id=None):
        for ports in self.adj_ports:
            if except_id is None or ports != except_id:
                self.send(ports, packet)

    def start_radar_routing(self):
        print('EVENT: IAB', self.donor_id, 'Start Radar Routing at', self.env.now)
        tag = 0
        while True:
            self.send_to_all_expect(RadarPacket(self.donor_id, tag))
            yield self.env.timeout(5)
            tag += 1
