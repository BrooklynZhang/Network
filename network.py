import simpy
import sys
import argparse

from link import Link
from packet import DataPacket
from flow import BaseFlow
from iabdonor import IAB_Donor
from iabnode import IAB_Node
from ue import UE


def main(filename):
    print("Setting up the Network")

    iabdonor_class = []
    iabnodes_class = []
    ue_class = []
    links_class = []

    devices_list = {}
    edges_list = []


    env = simpy.Environment()

    if filename:
        readlines = open(filename, 'r')

    for line in readlines:
        linelist = line.strip().split()
        if not linelist:
            continue
        print(linelist[0])

        if linelist[0][0] == 'D':
            donor = IAB_Donor(env, linelist[0])
            iabdonor_class.append(donor)
            devices_list[linelist[0]] = donor
        elif linelist[0][0] == 'N':
            node = IAB_Node(env, linelist[0])
            iabnodes_class.append(node)
            devices_list[linelist[0]] = node
        elif linelist[0][0] == 'U':
            ue = UE(env, linelist[0])
            ue_class.append(ue)
            devices_list[linelist[0]] = ue
        elif linelist[0][0] == 'L':
            link = Link(env, linelist[0], linelist[3], linelist[4], linelist[4])
            links_class.append(link)
            devices_list[linelist[0]] = link
            edges_list.append((linelist[0], linelist[1]))
            edges_list.append((linelist[0], linelist[2]))
        elif linelist[0][0] == 'F': #Flow Id / Source / Target / Data(MB) / Start Time
            flow = BaseFlow

    for elements in edges_list:
        l = devices_list[elements[0]]
        d = devices_list[elements[1]]

        l.add_port(elements[1], d)#link add port of device id: H/R#, port is host or router class
        d.add_port(elements[0], l)#hosts/routers add port of device id:L#, port is link


    env.run(until=5)

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("input_file", help="input file")
    args = arg_parser.parse_args()
    print(args.input_file)
    env = main(args.input_file)