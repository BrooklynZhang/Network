import simpy
import sys
import argparse

from router import Router
from host import Host
from link import Link
from packet import DataPacket


def main(filename):
    print("Setting up the Network")

    hostsclass = []
    routerclass = []
    linksclass = []

    deviceslist = {}
    edgeslist = []


    env = simpy.Environment()

    if filename:
        readlines = open(filename, 'r')

    for line in readlines:
        linelist = line.strip().split()
        if not linelist:
            continue
        print(linelist[0])

        if linelist[0][0] == 'H':
            host = Host(env, linelist[0])
            hostsclass.append(host)
            deviceslist[linelist[0]] = host
        elif linelist[0][0] == 'R':
            router = Router(env, linelist[0])
            routerclass.append(router)
            deviceslist[linelist[0]] = router
        elif linelist[0][0] == 'L':
            link = Link(env, linelist[0], linelist[3], linelist[4])
            linksclass.append(link)
            deviceslist[linelist[0]] = link
            edgeslist.append((linelist[0], linelist[1]))
            edgeslist.append((linelist[0], linelist[2]))

    for elements in edgeslist:
        l = deviceslist[elements[0]]
        d = deviceslist[elements[1]]

        l.add_port(elements[1], d)#link add port of device id: H/R#, port is host or router class
        d.add_port(elements[0], l)#hosts/routers add port of device id:L#, port is link


    env.run(until=5)

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("input_file", help="input file")
    args = arg_parser.parse_args()
    print(args.input_file)
    env = main(args.input_file)