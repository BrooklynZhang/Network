import matplotlib.pyplot as plt
import pickle
import argparse

class monitor(object):
    def __init__(self, iab_data, ue_time, link_time, link_usage):
        self.iab_donor_data = iab_data
        self.ue_time = ue_time
        self.link_time = link_time
        self.link_usage = link_usage


def collecting_data(iabdonor_class, iabnodes_class, ue_class, links_class):
    iab_data_dict = {}
    ue_transmit_time = {}
    link_transmit_time = {}
    link_usage_record = {}

    for iab_donor in iabdonor_class:
        iab_data_dict[iab_donor.donor_id] = iab_donor.monitor_transmission_t

    for ue in ue_class:
        ue_transmit_time[ue.ue_id] = ue.monitor_data_act_time

    for link in links_class:
        link_transmit_time[link.link_id] = link.monitor_transmission_t
        link_usage_record[link.link_id] = link.monitor_link_usage

    object = monitor(iab_data_dict, ue_transmit_time, link_transmit_time, link_usage_record)
    object = pickle.dumps(object)
    with open("dataset.txt", "wb") as FILE:
        FILE.write(object)
    FILE.close()

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


def make_response_time_graph(device_id, device_data_set):
    if device_id in device_data_set:
        dataset = device_data_set[device_id]
        flow_id_list = list(dataset.keys())
        print('INFO: Available flow id list to check: ', flow_id_list)
        id = input('Input: Please input the flow id that you want to check  ')
        data = dataset[id]
        sorted(data, key=lambda l: l[0])
        packet_no_list = [i[0] for i in data]
        response_time = [i[1] for i in data]
        graph_name = 'Responses time for Flow ' + id + ' of ' + device_id
        plt.title(graph_name)
        plt.ylabel('Average Response Time')
        plt.xlabel("Packet_Number")
        plt.bar(packet_no_list, response_time)
        plt.show()
    else:
        print('ERROR: No data for ', device_id)

def make_link_dataset_graph(device_id, device_data_set):
    if device_id in device_data_set:
        dataset = device_data_set[device_id]
        ports_list = list(dataset.keys())
        print('INFO: The are two direction(source port) of the link: ', ports_list)
        id = input('Input: Please input the source id for the source port link that you want to check  ')
        data = dataset[id]
        sorted(data, key=lambda l: l[0])
        time_list = [data[i][0] for i in range(0, len(data), 10)]
        level = [data[i][1] for i in range(0, len(data), 10)]
        graph_name = 'Level for link ' + id + ' of ' + device_id
        plt.title(graph_name)
        plt.ylabel('Level')
        plt.xlabel("Time")
        plt.bar(time_list, level)
        plt.show()

    else:
        print('ERROR: No data for ', device_id)

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("device_id1", help="input file")
    args = arg_parser.parse_args()
    print('EVENT: Generating monitor data of:', args.device_id1)

    with open("dataset.txt", "rb") as FILE:
        obj = pickle.loads(FILE.read())

    if args.device_id1[0] == 'D':
        iab_donor_dataset = obj.iab_donor_data
        make_response_time_graph(args.device_id1, iab_donor_dataset)

    elif args.device_id1[0] == 'U':
        ue_dataset = obj.ue_time
        make_response_time_graph(args.device_id1, ue_dataset)

    elif args.device_id1[0] == 'L':
        category = input("Please input 'usage' or 'time' to check different data:")
        if category == 'usage':
            link_usage_dataset = obj.link_usage
            make_link_dataset_graph(args.device_id1, link_usage_dataset)
        else:
            link_time_dataset = obj.link_time
            make_link_dataset_graph(args.device_id1, link_time_dataset)




