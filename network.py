import simpy
import sys
import argparse

from link import Link
from packet import DataPacket
from flow import BaseFlow
from iabdonor import IAB_Donor
from iabnode import IAB_Node
from ue import UE


def main(filename, algorithm):
    print("Setting Up The Network")

    iabdonor_class = []
    iabnodes_class = []
    ue_class = []
    links_class = []

    devices_list = {}
    edges_list = []
    flow_list = []


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
            devices_list[linelist[0]] = donor
        elif linelist[0][0] == 'N':
            node = IAB_Node(env, linelist[0], algorithm)
            iabnodes_class.append(node)
            devices_list[linelist[0]] = node
        elif linelist[0][0] == 'U':
            ue = UE(env, linelist[0], algorithm)
            ue_class.append(ue)
            devices_list[linelist[0]] = ue
        elif linelist[0][0] == 'L':
            link = Link(env, linelist[0], linelist[3], linelist[4], linelist[5], algorithm)
            links_class.append(link)
            devices_list[linelist[0]] = link
            edges_list.append((linelist[0], linelist[1]))
            edges_list.append((linelist[0], linelist[2]))
        elif linelist[0][0] == 'F': #Flow Id / Source / Target / Data(MB) / Start Time
            flow = BaseFlow(env, linelist[0], linelist[1], linelist[2], linelist[3], linelist[4], algorithm)
            flow_list.append(flow)

    for elements in edges_list:
        l = devices_list[elements[0]]
        d = devices_list[elements[1]]

        l.add_port(elements[1], d)#link add port of device id: H/R#, port is host or router class
        d.add_port(elements[0], l)#hosts/routers add port of device id:L#, port is link

    for iabnode in iabnodes_class:
        iabnode.initialize()

    for flow in flow_list:
        print(devices_list[flow.src_id].ue_id)
        devices_list[flow.src_id].add_flow(flow)


    env.run(until=5)

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("input_file", help="input file")
    arg_parser.add_argument("algorithm", help="algorithm")
    args = arg_parser.parse_args()
    print(args.input_file)
    print(args.algorithm)
    env = main(args.input_file, args.algorithm)