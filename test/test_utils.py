import os
import signal
import socket
import sys
import time
from json import dump
# from os import wait
from subprocess import Popen
from typing import Dict

import zmq

FOLLOWER = "Follower"
LEADER = "Leader"
CANDIDATE = "Candidate"

REQUEST_TIMEOUT = 1000  # milliseconds

processes = []


# def chld_handler(_signum, _frame):
#     wait()
#
#
# signal.signal(signal.SIGCHLD, chld_handler)


class Node:
    def __init__(self, program_file_path: str, config_path: str, i: int, config: dict):
        self.config = config
        self.i = i
        self.address = self.get_address()
        self.program_file_path = program_file_path
        self.config_path = os.path.abspath(config_path)
        self.startup_sequence = [
            "python",
            self.program_file_path,
            self.config_path,
            str(self.i),
        ]

        self.context = zmq.Context()
        self.req_socket = None
        self.reset_socket()

    def reset_socket(self):
        if self.req_socket is not None:
            self.req_socket.close()
        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.RCVTIMEO = REQUEST_TIMEOUT
        self.req_socket.connect(f"tcp://127.0.0.1:{self.get_port()}")

    def close_socket(self):
        self.req_socket.close()
        self.context.term()

    def send_json(self, message: Dict):
        try:
            self.req_socket.send_json(message)
        except Exception as e:
            self.reset_socket()
            raise zmq.error.ZMQError

    def recv_json(self):
        try:
            return self.req_socket.recv_json()
        except Exception as e:
            self.reset_socket()
            raise zmq.error.ZMQError

    def start(self, sleep=0):
        self.process = Popen(
            self.startup_sequence, stdout=sys.stdout, stderr=sys.stderr
        )
        self.pid = self.process.pid
        time.sleep(sleep)

    def terminate(self):
        self.close_socket()
        self.process.terminate()

    def kill(self):
        self.close_socket()
        self.process.kill()

    def wait(self):
        self.process.wait(5)

    def pause(self):
        self.process.send_signal(signal.SIGSTOP)

    def resume(self):
        self.process.send_signal(signal.SIGCONT)

    def commit_clean(self, sleep=0):
        time.sleep(sleep)
        self.clean(sleep)

    def clean(self, sleep=0):
        self.terminate()
        self.wait()
        self.kill()
        time.sleep(sleep)

    def restart(self, sleep=0):
        self.clean(sleep)
        self.start(sleep)
        time.sleep(sleep)

    def wait_for_startup(self):
        for i in range(1, 10):
            try:
                # print(f"Attempt {i} to connect to server at port {self.get_port()}")
                self.send_json({"type": "status", "method": "GET"})
                # print(f"Waiting for response from server at port {self.get_port()}")
                message = self.recv_json()
                # print(f"Successfully connected to server at port {self.get_port()}")
                # print(f"Client receive form server {self.get_port()}: {message}")
                assert "role" in message and "term" in message
                return
            except zmq.error.ZMQError as e:
                print(
                    f'Couldn\'t connect to server at port {self.get_port()} because of "{e}";'
                    f' trying again...'
                )
                time.sleep(1)

        raise Exception(f"Couldn't ever connect to server at port {self.get_port()}.")

    def get_port(self):
        address = self.config["addresses"][self.i]
        return address["port"]
    
    def get_internal_port(self):
        address = self.config["addresses"][self.i]
        return address["internal_port"]

    def get_address(self):
        address = self.config["addresses"][self.i]
        return address["ip"] + ":" + str(address["port"])

    def put_message(self, topic: str, message: str):
        data = {"type": "message", "method": "PUT", "topic": topic, "message": message}
        self.send_json(data)
        return self.recv_json()

    def put_message_without_topic(self, message: str):
        data = {"type": "message", "method": "PUT", "message": message}
        self.send_json(data)
        return self.recv_json()

    def put_message_without_message(self, topic: str):
        data = {"type": "message", "method": "PUT", "topic": topic}
        self.send_json(data)
        return self.recv_json()

    def get_message(self, topic: str):
        data = {"type": "message", "method": "GET", "topic": topic}
        self.send_json(data)
        return self.recv_json()

    def get_message_without_topic(self):
        data = {"type": "message", "method": "GET"}
        self.send_json(data)
        return self.recv_json()

    def message_without_method(self, topic: str):
        data = {"type": "message", "topic": topic}
        self.send_json(data)
        return self.recv_json()

    def put_topic(self, topic: str):
        data = {"type": "topic", "method": "PUT", "topic": topic}
        self.send_json(data)
        return self.recv_json()

    def get_topics(self):
        data = {"type": "topic", "method": "GET"}
        self.send_json(data)
        return self.recv_json()

    def topics_without_method(self):
        data = {"type": "topic"}
        self.send_json(data)
        return self.recv_json()

    def get_status(self):
        data = {"type": "status", "method": "GET"}
        self.send_json(data)
        return self.recv_json()

    def get_without_type(self):
        data = {"method": "GET"}
        self.send_json(data)
        return self.recv_json()

    def post_without_type(self):
        data = {"method": "POST"}
        self.send_json(data)
        return self.recv_json()


class Swarm:
    def __init__(self, program_file_path: str, num_nodes: int):
        self.num_nodes = num_nodes

        # create the config
        config = self.make_config()
        dump(config, open("config.json", "w"))

        self.nodes = [
            Node(program_file_path, "config.json", i, config)
            for i in range(self.num_nodes)
        ]

    def start(self, sleep=0):
        for node in self.nodes:
            node.start(sleep)
            node.wait_for_startup()
        time.sleep(sleep)

    def terminate(self):
        for node in self.nodes:
            node.terminate()

    def clean(self, sleep=0):
        for node in self.nodes:
            node.clean(sleep)
        time.sleep(sleep)

    def restart(self, sleep=0):
        for node in self.nodes:
            node.clean(sleep)
            node.start()
        time.sleep(sleep)

    def make_config(self):
        return {
            "addresses": [
                {
                    "ip": "127.0.0.1",
                    "port": get_free_port(),
                    "internal_port": get_free_port(),
                }
                for _ in range(self.num_nodes)
            ]
        }

    def get_status(self):
        statuses = {}
        for node in self.nodes:
            try:
                response = node.get_status()
                if "role" in response:
                    statuses[node.i] = response
            except zmq.error.ZMQError:
                continue
        return statuses

    def get_leader(self):
        for node in self.nodes:
            try:
                response = node.get_status()
                print(f"client get response from {node.get_port()}: {response}")
                if "role" in response and response["role"] == LEADER:
                    return node
            except zmq.error.ZMQError:
                continue
        time.sleep(0.5)
        return None

    def get_leader_loop(self, times: int):
        for _ in range(times):
            leader = self.get_leader()
            if leader:
                return leader
        return None

    def __getitem__(self, key):
        return self.nodes[key]


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    addr = s.getsockname()
    s.close()
    return addr[1]


if __name__ == "__main__":
    s = Swarm("config.json", 1)
    input()
    s.start()
