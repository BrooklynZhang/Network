import torch.nn as nn
import torch.nn.functional as F
import torch
import random
import collections


class DQN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, model1, model2, model3, model4):
        super(DQN, self).__init__()
        self.model1 = model1
        self.model2 = model2
        self.model3 = model3
        self.model4 = model4
        self.fc1 = nn.Linear(input_size, hidden_size),
        self.fc2 = nn.Linear(hidden_size, hidden_size),
        self.fc3 = nn.Linear(hidden_size, output_size)

    def forward(self, state):
        model1 = self.model1(state[0])
        model2 = self.model2(state[1])
        model3 = self.model3(state[2])
        model4 = self.model4(state[3])
        model = torch.cat((model1, model2, model3, model4), dim=1)
        x = self.fc1(model)
        x = self.fc2(F.relu(x))
        x = self.fc3(F.relu(x))
        return x


class INPUT_NN(nn.Module):
    def __init__(self, input_size, output_size):
        super(INPUT_NN, self).__init__()
        self.fc = nn.Linear(input_size, output_size)

    def forward(self, x):
        x = self.fc(x)
        return x


class ReplayBuffer(object):
    def __init__(self, action_size, buffer_size, batch_size):
        self.action_size = action_size
        self.memory = collections.deque(maxlen=buffer_size)
        self.batch_size = batch_size
        self.experiences = collections.namedtuple("Experience", field_names=["state",
                                                                 "action",
                                                                 "reward",
                                                                 "next_state",
                                                                 "done"])

    def add(self, state, action, reward, next_state, done):
        e = self.experiences(state, action, reward, next_state, done)
        self.memory.append(e)

    def sample(self):
        return random.sample(self.memory, k=self.batch_size)

