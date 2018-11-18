import numpy as np
from collections import defaultdict
from agents.core import Greedy, EpsilonGreedy


class MonteCarlo:

    def __init__(self, env, agent, style='every'):
        self.env = env
        self.nS = env.nS
        self.nA = env.nA

        self.agent = agent
        self.policy = agent.policy
        # self.greedy = Greedy(self.agent.values)
        # self.epsilon_greedy = EpsilonGreedy(self.agent.values)
        self.discount = agent.discount

        self.style = style

    def value_prediction(self, steps: int = 1000, episodes: int = 100) -> None:
        """
        This function performs monte carlo value prediction. This is achieved my sampling a number of episodes using the
        current policy and predicting values of states according to these episodes.
        :param steps: The maximum amount of steps taken in an episode
        :param episodes: The number of episodes to run value prediction for
        :param style: if style is 'first' only the first encounters of each state in an episode are considered, if style
            is 'every' then every encounter of a state is considered in each episode
        """

        V = self.agent.values
        Q = self.agent.q_values

        # Number of times states have been visited over all episodes
        N = defaultdict(int)

        # Number of times state/action pairs have been visited over all episodes
        Q_N = defaultdict(lambda: defaultdict(int))

        for e in range(episodes):
            episode, state_visits, Q_visits = self.generate_episode(N, Q_N, steps)

            # Backtracking from the end to the start of the episode calculating the returns
            ret = 0
            for step in episode[::-1]:
                _, _, reward = step
                ret = self.discount * ret + reward
                step.append(ret)

            # Updating value estimates
            for obs in visits:
                sum_returns = sum([episode[t][3] for t in visits[obs]])
                n = len(visits[obs])
                V[obs] = V[obs] + (1/N[obs]) * (sum_returns - n*V[obs])

    def generate_episode(self, N: defaultdict, Q_N: defaultdict, steps: int) -> (list, defaultdict, defaultdict):
        """
        This function generates a single episode by sampling and taking actions according to the policy until a done
        state is reached or the maximum number of steps have been taken
        :param N: N is the dictionary keeping track of the total number of visits to states over all episodes
        :param Q_N: Q_N is the dictionary keeping track of the total number of visits to state/actions pairs over all
            episodes
        :param steps: The maximum number of steps to take in the episode
        :return: a tuple (episode, state_visits, q_visits)
            episode         -> The generated episode which is a list containing (state, action, reward) tuples for each
                time step
            state_visits    -> A dictionary giving the timesteps at which states were visited this episode
            q_visits        -> A dictionary giving the timesteps at which state/action pairs were visited this episode
        """
        obs = self.env.reset()
        episode = []

        # Tracks the time steps where each state was encountered during this episode
        state_visits = defaultdict(list)

        # Tracks the time steps where each state/action pair was encountered during this episode
        Q_visits = defaultdict(lambda: defaultdict(list))

        for t in range(steps):
            action = self.policy.sample(obs)
            next_obs, reward, done, _ = self.env.step(action)
            episode.append([int(obs), int(action), reward])

            if self.style == 'every':
                state_visits[obs].append(t)
                N[obs] += 1
                Q_visits[obs][action].append(t)
                Q_N[obs][action] += 1
            elif self.style == 'first':
                if obs not in visits:
                    state_visits[obs].append(t)
                    N[obs] += 1
                if action not in Q_visits[obs]:
                    Q_visits[obs][action].append(t)
                    Q_N[obs][action] += 1

            if done:
                break
            obs = next_obs

        return episode, state_visits, Q_visits

    def q_prediction(self, style = 'first', max_steps = 1000, max_episodes=100):

        num_visits = defaultdict(lambda: defaultdict(int))

        for e in range(max_episodes):
            obs = self.env.reset()

            episode = []
            visits = defaultdict(lambda: defaultdict(list))
            for t in range(max_steps):
                action = self.policy.sample_action(obs)
                next_obs, reward, done, _ = self.env.step(action)
                episode.append([obs, action, reward])

                if (style == 'every') or (style == 'first' and not action in visits[obs]):
                    visits[obs][action].append(t)
                    num_visits[obs][action] += 1

                if done:
                    break
                obs = next_obs

            ret = 0
            for step in episode[::-1]:
                _, _, reward = step
                ret = self.discount_factor * ret + reward
                step.append(ret)

            for obs in visits:
                for action in visits[obs]:
                    visited_timesteps = visits[obs][action]
                    n = len(visited_timesteps)
                    sum_returns = sum([episode[t][3] for t in visited_timesteps])
                    old_value = self.agent.get_q_value(int(obs), action)
                    new_value = old_value + (1/num_visits[obs][action]) * (sum_returns - n*old_value)
                    self.agent.set_q_value(int(obs), action, new_value)

    def off_policy_q_prediction(self, max_steps = 1000, max_episodes=100, style='every'):
        target = self.greedy
        behaviour = self.epsilon_greedy

        cum_weights = defaultdict(lambda: defaultdict(int))

        for e in range(max_episodes):
            if e % 10 == 0:
                print("episode {}".format(e))
            obs = self.env.reset()

            episode = []
            visits = defaultdict(lambda: defaultdict(list))
            for t in range(max_steps):
                action = behaviour.sample_action(obs)
                next_obs, reward, done, _ = self.env.step(action)
                episode.append([obs, action, reward])

                if style == 'every':
                    visits[obs][action].append(t)

                if done:
                    break
                obs = next_obs

            ret = 0
            weight = 1
            for step in episode[::-1]:
                obs, action, reward = step
                ret = self.discount_factor * ret + reward
                cum_weights[obs][action] += weight
                old_value = self.agent.get_q_value(int(obs), action)
                new_value = old_value + (weight/cum_weights[obs][action]) * (ret - old_value)
                self.agent.set_q_value(int(obs), action, new_value)

                importance_ratio = (target.get_action_prob(obs, action) /
                                     behaviour.get_action_prob(obs, action))
                weight = weight * importance_ratio
                if weight == 0:
                    break

    def off_policy_q_iteration(self, max_steps = 5000, max_episodes=100, true_values=None):
        target = self.greedy
        behaviour = self.epsilon_greedy

        cum_weights = defaultdict(lambda: defaultdict(int))

        for e in range(max_episodes):
            if e % 100 == 0:
                print("episode {}".format(e))
                if not true_values is None:
                    print("error {}".format(np.linalg.norm(true_values - np.array(self.agent.values.get_all_q_values()))))
            obs = self.env.reset()


            episode = []
            visits = defaultdict(lambda: defaultdict(list))
            for t in range(max_steps):
                action = behaviour.sample_action(obs)
                next_obs, reward, done, _ = self.env.step(action)
                episode.append([obs, action, reward])
                visits[obs][action].append(t)
                if done:
                    break
                obs = next_obs

            ret = 0
            weight = 1
            for step in episode[::-1]:
                obs, action, reward = step
                ret = self.discount_factor * ret + reward
                cum_weights[obs][action] += weight
                old_value = self.agent.get_q_value(int(obs), action)
                new_value = old_value + (weight/cum_weights[obs][action]) * (ret - old_value)
                self.agent.set_q_value(int(obs), action, new_value)
                if action != target.sample_action(obs):
                    break
                importance_ratio = (1 / behaviour.get_action_prob(obs, action))
                weight = weight * importance_ratio

    def policy_improvement(self, type = 'greedy'):

        for state in range(self.num_states):
            optimal_action = None
            maxval = None

            for action in range(self.num_actions):
                val = self.agent.get_q_value(state, action)

                if maxval is None or val > maxval:
                    optimal_action = action
                    maxval = val

            if type == 'greedy':
                self.policy.set_optimal_action(state, optimal_action)
            elif type == 'epsilon_greedy':
                self.policy.set_optimal_action(state, optimal_action, epsilon = 0.1)

    def policy_iteration(self, style = 'first', max_steps = 1000, max_episodes=10, type='greedy'):
        for _ in range(10):
            print(_)
            self.q_prediction(style, max_steps, max_episodes)
            self.policy_improvement(type=type)

    def value_iteration(self, style = 'first', max_steps = 1000, type='optimal'):
        for _ in range(100):
            self.q_prediction(style, max_steps, max_episodes=1)
            self.policy_improvement(type=type)
