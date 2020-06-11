import matplotlib.pyplot as plt

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
