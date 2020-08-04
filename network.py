import simpy
import sys
import argparse

import gui
import collections
from link import Link
from flow import BaseFlow
from iabdonor import IAB_Donor
from iabnode import IAB_Node
from ue import UE


def main(filename, algorithm):
    node_donor_link = ['L0', 'D1', 'ND1', '1000', '0', '999999999', 'y']
    iabdonor_class = []
    iabnodes_class = []
    ue_class = []
    links_class = []
    iab_id_list = []
    rate_list = collections.deque()
    devices_list = {}
    edges_list = []
    flow_list = []
    legacy = 'n'


    env = simpy.Environment()

    if filename:
        readlines = open(filename, 'r')

    for line in readlines:
        linelist = line.strip().split()
        if not linelist:
            continue

        if linelist[0][0] == 'D':
            donor = IAB_Donor(env, linelist[0], algorithm)
            iabdonor_class.append(donor)
            iab_id_list.append(linelist[0])
            devices_list[linelist[0]] = donor
            link = Link(env, node_donor_link[0], node_donor_link[3], node_donor_link[4], node_donor_link[5], node_donor_link[6], rate_list, algorithm)
            links_class.append(link)
            devices_list[node_donor_link[0]] = link
            edges_list.append((node_donor_link[0], node_donor_link[1]))
            edges_list.append((node_donor_link[0], node_donor_link[2]))
        elif linelist[0][0] == 'N':
            node = IAB_Node(env, linelist[0], algorithm, legacy, filename)
            iab_id_list.append(linelist[0])
            iabnodes_class.append(node)
            devices_list[linelist[0]] = node
        elif linelist[0][0] == 'U':
            ue = UE(env, linelist[0], algorithm)
            ue_class.append(ue)
            devices_list[linelist[0]] = ue
        elif linelist[0][0] == 'L':
            link = Link(env, linelist[0], linelist[3], linelist[4], linelist[5], linelist[6], rate_list, algorithm)
            links_class.append(link)
            devices_list[linelist[0]] = link
            edges_list.append((linelist[0], linelist[1]))
            edges_list.append((linelist[0], linelist[2]))
        elif linelist[0][0] == 'F':
            flow = BaseFlow(env, linelist[0], linelist[1], linelist[2], linelist[3], linelist[4], linelist[5], linelist[6], algorithm)
            flow_list.append(flow)
        elif linelist[0] == 'running_time':
            running_time = float(linelist[1])
        elif linelist[0] == 'monitor':
            b_monitor = linelist[1]
        elif linelist[0] == 'rate_list':
            for i in range(1, len(linelist) - 1):
                rate_list.append(float(linelist[i]))
        elif linelist[0] == 'legacy':
            legacy = linelist[1]

    for elements in edges_list:
        l = devices_list[elements[0]]
        d = devices_list[elements[1]]

        l.add_port(elements[1], d)#link add port of device id: H/R#, port is host or router class
        d.add_port(elements[0], l)#hosts/routers add port of device id:L#, port is link

    for iabnode in iabnodes_class:
        iabnode.iab_id_list = iab_id_list
        iabnode.initialize()

    for flow in flow_list:
        devices_list[flow.src_id].add_flow(flow)

    if b_monitor == 'y':
        for l in links_class:
            l.monitor_process(running_time)

    env.run(until=running_time)
    gui.collecting_data(args.algorithm, filename, iabdonor_class, iabnodes_class, ue_class, links_class)


    print('EVENT: Simulation Finished')

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("input_file", help="input file")
    arg_parser.add_argument("algorithm", help="algorithm")
    args = arg_parser.parse_args()
    print('EVENT: The Test Case File is:', args.input_file)
    print('EVENT: The Algorithm is:', args.algorithm)
    env = main(args.input_file, args.algorithm)