import matplotlib.pyplot as plt
import pickle
import argparse
import numpy as np
import torch

algs = ['ant', 'q', 'dijkstra', 'dqn']

class monitor(object):
    def __init__(self, iab_data, ue_time, link_time, link_usage, link_packet_loss):
        self.iab_donor_data = iab_data
        self.ue_time = ue_time
        self.link_time = link_time
        self.link_usage = link_usage
        self.link_packet_loss = link_packet_loss

class dqndata(object):
    def __init__(self, models, memory):
        self.models = models
        self.memory = memory


def collecting_data(algorithm, test_case, iabdonor_class, iabnodes_class, ue_class, links_class):
    iab_data_dict = {}
    ue_transmit_time = {}
    link_transmit_time = {}
    link_usage_record = {}
    link_packet_loss = {}

    for iab_donor in iabdonor_class:
        iab_data_dict[iab_donor.donor_id] = iab_donor.monitor_transmission_t

    for ue in ue_class:
        ue_transmit_time[ue.ue_id] = ue.monitor_data_act_time

    for link in links_class:
        link_transmit_time[link.link_id] = link.monitor_transmission_t
        link_usage_record[link.link_id] = link.monitor_link_usage
        link_packet_loss[link.link_id] = link.monitor_packet_loss

    object = monitor(iab_data_dict, ue_transmit_time, link_transmit_time, link_usage_record, link_packet_loss)
    object = pickle.dumps(object)
    filename = algorithm + "dataset.txt"
    with open(filename, "wb") as FILE:
        FILE.write(object)
    FILE.close()

    if algorithm == 'dqn':
        for iab in iabnodes_class:
            state = {'net':iab.model_local.state_dict(), 'opt':iab.optimizer.state_dict()}
            torch.save(state, iab.node_id + ".pth")


def create_the_graph(link_id, link_dict):
    name_list = list(link_dict.keys())
    data_list = list(link_dict.values())

    for i in range(len(data_list)):
        data = data_list[i]
        if i == 0:
            graph_name = str(link_id) + ' : ' + str(name_list[i]) + ' to ' + str(name_list[1])
        else:
            graph_name = str(link_id) + ' : ' + str(name_list[1]) + ' to ' + str(name_list[0])
        x_list = []
        y_list = []
        for d in data:
            x_list.append(d[0])
            y_list.append(d[1])
        plt.title(graph_name)
        plt.xlabel("environment time")
        plt.ylabel("level for the link")
        plt.plot(x_list, y_list)
        plt.show()

def make_total_response_time_graph(device_id, device_data_set):
    fig, ax = plt.subplots()
    plt.ylabel('transmitting time')
    plt.xlabel('packet number')
    for name in algs:
        algdataset = device_data_set[name]
        dataset = algdataset[device_id]
        data = dataset['F1']
        data.sort(key=lambda l: l[0])
        y = []
        x = [data[i][0] for i in range(0, len(data) - 5, 5)]
        #y = [data[i][1] for i in range(0, len(data), 10)]
        for j in range(0, len(data) - 5, 5):
            list = [data[i][1] for i in range(j, j + 5)]
            y.append(np.mean(list)/10)
        print(name, np.mean(y))
        ax.plot(x, y, label=name)
    ax.legend()
    plt.show()

def make_response_time_graph(device_id, device_data_set, algorithm):
    if device_id in device_data_set:
        dataset = device_data_set[device_id]
        flow_id_list = list(dataset.keys())
        print('INFO: Available flow id list to check: ', flow_id_list)
        id = input('Input: Please input the flow id that you want to check  ')
        data = dataset[id]

        option = input('1. Percentage or 2. Specific  ')
        if option == '1':
            data.sort(key=lambda l: l[1])
            x = [len(data) * i // 10 for i in range(1, 10)]
            y = [round(data[i][1], 4) for i in x]
            graph_name = 'Responses time for Flow ' + id + ' of ' + device_id + ' based on Algorithm ' + algorithm
            plt.title(graph_name)
            plt.ylabel('Average Response Time')
            plt.xlabel("Packet_Amount")
            bars = plt.bar([str(x[i-1]) + ' -' + str(i*10) + '%' for i in range(1,10)], y)
            for bar in bars:
                yval = bar.get_height()
                plt.text(bar.get_x(), yval + .005, yval)
            plt.show()
        else:
            data.sort(key=lambda l: l[0])
            x = [data[i][0] for i in range(0, len(data), 10)]
            y = [data[i][1] for i in range(0, len(data), 10)]
            graph_name = 'Responses time for Flow ' + id + ' of ' + device_id + ' based on Algorithm ' + algorithm
            plt.title(graph_name)
            plt.xlabel("Packet Number")
            plt.ylabel("Transmittion Time")
            plt.plot(x, y)
            plt.show()
    else:
        print('ERROR: No data for ', device_id)

def make_link_dataset_graph(device_id, device_data_set, category, algorithm):
    if device_id in device_data_set:
        dataset = device_data_set[device_id]
        ports_list = list(dataset.keys())
        print('INFO: The are two direction(source port) of the link: ', ports_list)
        id = input('Input: Please input the source id for the source port link that you want to check  ')
        data = dataset[id]
        sorted(data, key=lambda l: l[0])
        time_list = [data[i][0] for i in range(0, len(data), 10)]
        level = [data[i][1] for i in range(0, len(data), 10)]
        if category == 'usage':
            plt.ylabel('Level')
            graph_name = 'Level for link ' + id + ' of ' + device_id + ' based on Algorithm ' + algorithm
        elif category == 'time':
            plt.ylabel('transmitting time')
            graph_name = 'Transmitting time ' + id + ' of ' + device_id + ' based on Algorithm ' + algorithm
        elif category == 'packet':
            plt.ylabel('Packet Loss Amount')
            graph_name = 'Total Packet Loss ' + id + ' of ' + device_id + ' based on Algorithm ' + algorithm

        plt.title(graph_name)
        plt.xlabel("Time")
        plt.bar(time_list, level)
        plt.show()
    else:
        print('ERROR: No data for ', device_id)

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("algorithm", help="algorithm")
    arg_parser.add_argument("device_id1", help="input file")
    args = arg_parser.parse_args()
    print('EVENT: Generating monitor data of:', args.device_id1)
    if args.algorithm == 'all':
        dataset = {}
        for name in algs:
            filename = name + "dataset.txt"
            with open(filename, "rb") as FILE:
                obj = pickle.loads(FILE.read())
                if args.device_id1[0] == 'D':
                    iab_donor_dataset = obj.iab_donor_data
                    dataset[name] = iab_donor_dataset
            FILE.close()
        make_total_response_time_graph(args.device_id1, dataset)

    else:
        filename = args.algorithm + "dataset.txt"
        with open(filename, "rb") as FILE:
            obj = pickle.loads(FILE.read())

        if args.device_id1[0] == 'D':
            iab_donor_dataset = obj.iab_donor_data
            make_response_time_graph(args.device_id1, iab_donor_dataset, args.algorithm)

        elif args.device_id1[0] == 'U':
            ue_dataset = obj.ue_time
            make_response_time_graph(args.device_id1, ue_dataset, args.algorithm)

        elif args.device_id1[0] == 'L':
            category = input("Please input 'usage', 'packet' or 'time' to check different data:")
            if category == 'usage':
                link_usage_dataset = obj.link_usage
                make_link_dataset_graph(args.device_id1, link_usage_dataset, category, args.algorithm)
            elif category == 'time':
                link_time_dataset = obj.link_time
                make_link_dataset_graph(args.device_id1, link_time_dataset, category, args.algorithm)
            elif category == 'packet':
                link_packet_loss = obj.link_packet_loss
                make_link_dataset_graph(args.device_id1, link_packet_loss, category, args.algorithm)




