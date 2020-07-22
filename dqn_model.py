import torch.nn as nn
import torch.nn.functional as F
import torch
import random
import collections
import numpy as np

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class DQN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, model1, model2, model3, model4):
        super(DQN, self).__init__()
        self.model1 = model1
        self.model2 = model2
        self.model3 = model3
        self.model4 = model4
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.lstm = nn.LSTM(hidden_size, hidden_size, 1, batch_first=True)
        self.fc3 = nn.Linear(hidden_size, output_size)

    def forward(self, input0, input1, input2, input3, input4, input5):
        model1 = self.model1(input0)
        model2 = self.model2(input1)
        model3 = self.model3(input2)
        model4 = self.model4(input3)
        model = torch.cat((model1, model2, model3, model4), dim=1)
        x = self.fc1(model)
        x = self.fc2(torch.sigmoid(x))
        x, (h, c) = self.lstm(torch.sigmoid(x).unsqueeze(1), (input4, input5))
        x = self.fc3(x.squeeze(1))
        x = torch.sigmoid(x)
        x = torch.neg(x)
        return x, (h, c)

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
        self.experiences = collections.namedtuple("Experience", field_names=["state0",
                                                                             "state1",
                                                                             "state2",
                                                                             "state3",
                                                                             "action",
                                                                             "reward",
                                                                             "hidden_state0",
                                                                             "hidden_state1",
                                                                             "next_state0",
                                                                             "next_state1",
                                                                             "next_state2",
                                                                             "next_state3",
                                                                             "done"])

    def add(self, state, action, reward, hidden_state0, hidden_state1, next_state, done):
        e = self.experiences(state[0], state[1], state[2], state[3], action, reward, hidden_state0, hidden_state1, next_state[0], next_state[1], next_state[2], next_state[3], done)
        self.memory.append(e)

    def sample(self):
        experiences = random.sample(self.memory, k=self.batch_size)
        states0 = torch.from_numpy(np.vstack([e.state0 for e in experiences if e is not None])).float().to(device)
        states1 = torch.from_numpy(np.vstack([e.state1 for e in experiences if e is not None])).float().to(device)
        states2 = torch.from_numpy(np.vstack([e.state2 for e in experiences if e is not None])).float().to(device)
        states3 = torch.from_numpy(np.vstack([e.state3 for e in experiences if e is not None])).float().to(device)
        actions = torch.from_numpy(np.vstack([e.action for e in experiences if e is not None])).long().to(device)
        rewards = torch.from_numpy(np.vstack([e.reward for e in experiences if e is not None])).float().to(device)
        hidden_state0 = torch.from_numpy(np.vstack([e.hidden_state0[0] for e in experiences if e is not None])).float().to(device)
        hidden_state0 = hidden_state0.unsqueeze(0)
        hidden_state1 = torch.from_numpy(np.vstack([e.hidden_state1[0] for e in experiences if e is not None])).float().to(device)
        hidden_state1 = hidden_state1.unsqueeze(0)
        next_states0 = torch.from_numpy(np.vstack([e.next_state0 for e in experiences if e is not None])).float().to(device)
        next_states1 = torch.from_numpy(np.vstack([e.next_state1 for e in experiences if e is not None])).float().to(device)
        next_states2 = torch.from_numpy(np.vstack([e.next_state2 for e in experiences if e is not None])).float().to(device)
        next_states3 = torch.from_numpy(np.vstack([e.next_state3 for e in experiences if e is not None])).float().to(device)
        dones = torch.from_numpy(np.vstack([e.done for e in experiences if e is not None])).float().to(device)
        return (states0, states1, states2, states3, actions, rewards, hidden_state0, hidden_state1,next_states0, next_states1, next_states2, next_states3, dones)

    def __len__(self):
        """Return the current size of internal memory."""
        return len(self.memory)

