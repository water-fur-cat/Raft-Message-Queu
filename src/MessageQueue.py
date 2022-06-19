import sys, time, zmq, json, uuid

from threading import Thread

from role import Role
from ElectionNode import ElectionNode

HOST = "tcp://127.0.0.1:"


class MessageQueue(ElectionNode):
    def __init__(self, port, internal_port, index, sibling_nodes):
        super().__init__(internal_port, index, sibling_nodes)

        self.port = port

        """
        For client
        """
        self.socket = self.context.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind(f"{HOST}{port}")
        # print(f"Bound server {port}")

        # listen to client
        clientFollower = Thread(target=self.listenToClient)
        clientFollower.start()

    def listenToClient(self):
        # print(f"Sever {self.index} at {self.port} start listening to client")
        while True:
            try:
                message = self.socket.recv_json()
                # print(f"Server at {self.port} received message {message}")
                self.response_to_node(message)
                # time.sleep(0.01)
            except KeyboardInterrupt:
                self.socket.close()
                self.context.term()

    """
    For responses to client
    """

    # response to request based on types
    def response_to_node(self, message):
        if "type" not in message:
            print(f"Server: No type in request.")
            self.socket.send_json({"success": False})

        if message["type"] == "status":
            # 1. check for status
            self.response_to_status_request(message)
        else:
            # topic/message requests: separate response for different roles
            if not self.role == Role.LEADER:
                print(f"I am a {self.role.value}")
                self.socket.send_json({"success": False})
            else:
                messageId = int(uuid.uuid4())
                if self.total_nodes == 1:
                    self.client_messages_state[messageId] = True
                else:
                    # 1. send to followers
                    self.client_messages_state[messageId] = False
                    self.send_followers_client_request(message, messageId)

                # 2. get more than half agree: reply to client
                while not self.client_messages_state[messageId]:
                    time.sleep(0.02)

                # done commit
                # print("done commit")
                if message["type"] == "topic":
                    # 2. topics
                    self.response_to_topics_request(message)

                elif message["type"] == "message":
                    # 3. message
                    self.response_to_message_request(message)

                else:
                    self.socket.send_json({"I have no idea": False})
                # messageCommitChecker = Thread(target=self.check_message_commit, args=(message, messageId))
                # messageCommitChecker.start()

    def check_message_commit(self, message, messageId):
        print(self.client_messages_state)
        while True:
            # check status
            if not self.client_messages_state[messageId]:
                # time.sleep(0.01)
                continue

            # done commit
            print("done commit")
            if message["type"] == "topic":
                # 2. topics
                self.response_to_topics_request(message)

            elif message["type"] == "message":
                # 3. message
                self.response_to_message_request(message)

            else:
                self.socket.send_json({"I have no idea": False})
            break

    # response to requests of topics
    def response_to_topics_request(self, message):
        if "method" not in message:
            print(f"Server: No method in request.")
            self.socket.send_json({"success": False})
            return

        if message["method"] == 'PUT':
            # 2.1. create topic
            if "topic" not in message:
                print(f"Server: No topic in request.")
                self.socket.send_json({"success": False})
                return
            self.socket.send_json({"success": self.create_topic(message["topic"])})
        elif message["method"] == 'GET':
            # 2.2. get topics
            self.socket.send_json({"success": True, "topics": self.get_topic()})
        else:
            self.socket.send_json({"success": False})

    # response to requests of message
    def response_to_message_request(self, message):
        if "method" not in message or "topic" not in message:
            print(f"Server: No method or no topic in request.")
            self.socket.send_json({"success": False})
            return

        if message["method"] == 'PUT':
            # 3.1. add a message
            if "message" not in message:
                print(f"Server: No message in request.")
                self.socket.send_json({"success": False})
                return
            self.socket.send_json({"success": self.add_message(message["topic"], message["message"])})
        elif message["method"] == 'GET':
            # 3.2. pop a message from the topic
            status, pop_message = self.get_message(message["topic"])
            if status:
                self.socket.send_json({"success": status, "message": pop_message})
            else:
                self.socket.send_json({"success": False})
        else:
            self.socket.send_json({"success": False})

    # # response to requests of status
    def response_to_status_request(self, message):
        if "method" not in message:
            print(f"Server: No method in request.")
            self.socket.send_json({"success": False})
            return

        if message['method'] == 'GET':
            self.socket.send_json({'role': self.role.value, 'term': self.term})
        else:
            self.socket.send_json({"success": False})


if __name__ == "__main__":
    _this_file_name, config_path, node_id = sys.argv
    node_id = int(node_id)

    config_json = json.load(open(config_path))
    port = config_json["addresses"][node_id]["port"]
    internal_port = config_json["addresses"][node_id]["internal_port"]
    server_config = config_json['addresses']

    nodes = [{"ip": server['ip'], "port": server['port'], "internal_port": server['internal_port']} for server in
             server_config]
    sibling_nodes = ['{}'.format(node["internal_port"]) for idx, node in enumerate(nodes) if
                     idx != node_id]

    node = MessageQueue(port, internal_port, node_id, sibling_nodes)
