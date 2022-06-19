from email import message
from shutil import register_archive_format
import pytest, zmq, json
import time
from threading import RLock, Thread
WAIT_TIME_TO_CONNECT_PEERS = 1

from test_utils import Swarm, LEADER, FOLLOWER

# seconds the program will wait after starting a node for election to happen
# it is set conservatively, you will likely be able to lower it for faster testing
ELECTION_TIMEOUT = 2.0

# array of numbr of nodes spawned on tests, an example could be [3,5,7,11,...]
# default is only 5 for faster tests
NUM_NODES_ARRAY = [5]

# your `node.py` file path
PROGRAM_FILE_PATH = "../src/node.py"
HOST = "tcp://127.0.0.1:"
context = zmq.Context()

class ZMQSender:
    def __init__(self, internal_port):
        self.internal_port = internal_port
        self.internal_socket = context.socket(zmq.ROUTER)
        self.internal_socket.setsockopt(zmq.IDENTITY, f"{self.internal_port}".encode())
        self.internal_socket.bind(f"{HOST}{internal_port}")
        self.reentrant_lock = RLock()
        self.message = None
        # give time to actually connect
        time.sleep(WAIT_TIME_TO_CONNECT_PEERS)
        internalFollower = Thread(target=self.listenToInternal)
        internalFollower.start()
        internalConnection = Thread(target=self.connectToInernal)
        internalConnection.start()

    def send_to_peer(self, peer_id, message):
        self.reentrant_lock.acquire()
        print(self.internal_socket, f'sending "{message}" to', peer_id)
        self.internal_socket.send_multipart([f"{HOST}{peer_id}".encode(), message.encode()])
        self.reentrant_lock.release()
    
    def connectToInernal(self):
        self.internal_socket.connect(f"{HOST}57779")
        # print(f"Internal: connecting to {HOST}{port}")
        # give time to actually connect
        time.sleep(WAIT_TIME_TO_CONNECT_PEERS)

    def listenToInternal(self):
        # print(f"Internal: Sever {self.index} at {self.internal_port} start listening to sibling_nodes")
        while True:
            try:
                print(f"{self.internal_port} trying to recv...")
                sender_message = self.internal_socket.recv_multipart()
                message = json.loads(sender_message.decode())
                self.message = message
                print(f"Internal: Server at {self.internal_port} received internal message {message}")
            except KeyboardInterrupt:
                self.internal_socket.close()
                self.context.term()

@pytest.fixture
def swarm(num_nodes):
    swarm = Swarm(PROGRAM_FILE_PATH, num_nodes)
    try:
        swarm.start(ELECTION_TIMEOUT)
        yield swarm
    finally:
        swarm.clean()

# @pytest.mark.parametrize('num_nodes', [1])
# def test_vote_leader_success(swarm: Swarm, num_nodes: int):
#     sender = ZMQSender(50123)
#     message = {
#             'term': 4,
#             'candidateId': 3,
#             'internal_port': 50123
#         }
#     # sender.send_to_peer(swarm[0].get_internal_port(),json.dumps(message))
#     sender.send_to_peer(57779,json.dumps(message))
#     response = json.loads(sender.message)
#     print(response)
#     assert response['vote'] == False
