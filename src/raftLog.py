import json
from dataclasses import dataclass


@dataclass
class LogEntry:
    message: str
    term: int
    agreeCounter: int


class RaftLog:
    def __init__(self):
        self.messages = {}
        self.client_messages_state = {}

        self.logs = []
        self.entries = []
        self.log_size = self.get_log_size()

        self.transaction_log = {}

    def get_log_size(self):
        return len(self.logs)

    def get_last_log_index(self):
        return len(self.logs) - 1

    def get_pre_log_term(self, pre_index):
        return self.logs[pre_index].term if pre_index > -1 else -1

    def get_pre_log_entry(self, pre_index):
        return self.logs[pre_index].message if pre_index > -1 else ""

    def get_last_log_term(self):
        return self.logs[self.get_last_log_index()].term if len(self.logs) else -1

    def get_last_log_entry(self):
        return self.logs[self.get_last_log_index()].message if len(self.logs) else ""

    def create_new_log(self, entityId, message, term, agreeCount=1):
        new_log = LogEntry(message=message, term=term, agreeCounter=agreeCount)
        self.transaction_log[entityId] = new_log

    # response to request based on types
    def manage_commit_log(self, message, term, agreeCount=1):
        if not isinstance(message, dict):
            message = json.loads(message)

        # add log
        commit_log = LogEntry(message=message, term=term, agreeCounter=agreeCount)
        self.logs.append(commit_log)
        # print(f"follower log: {self.logs}")

        # execute message
        if message["type"] == "topic":
            # 2. topics
            self.manage_topics(message)

        elif message["type"] == "message":
            # 3. message
            self.manage_message(message)

    # response to requests of topics
    def manage_topics(self, message):
        if "method" not in message:
            return

        if message["method"] == 'PUT':
            # 2.1. create topic
            if "topic" not in message:
                return
            self.create_topic(message["topic"])
        elif message["method"] == 'GET':
            # 2.2. get topics
            self.get_topic()

    # response to requests of message
    def manage_message(self, message):
        if "method" not in message or "topic" not in message:
            return

        if message["method"] == 'PUT':
            # 3.1. add a message
            if "message" not in message:
                return
            self.add_message(message["topic"], message["message"])
        elif message["method"] == 'GET':
            # 3.2. pop a message from the topic
            status, pop_message = self.get_message(message["topic"])

    # get topics in message queue
    def get_topic(self):
        return list(self.messages.keys())

    # create topic
    def create_topic(self, topic):
        # if topic name does not exist: return False
        if topic in self.messages:
            # print(f"Server: Topic {topic} already exist.")
            return False

        self.messages[topic] = []
        # print(f"Server: Topic {topic} created.")
        return True

    # pop a message
    def get_message(self, topic):
        # if topic name does not exist: return False
        if topic not in self.messages:
            # print(f"Server: Topic {topic} does not exist.")
            return False, ""

        # if no message
        if len(self.messages[topic]) == 0:
            # print(f"Server: Topic {topic} has no message.")
            return False, ""

        return True, self.messages[topic].pop(0)

    # add message to topic
    def add_message(self, topic, message):
        if topic not in self.messages:
            # print(f"Server: Topic {topic} does not exist.")
            return False

        self.messages[topic].append(message)
        # print(f"Server: Message {message} appended to topic {topic}.")
        return True

