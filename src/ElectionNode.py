import sys, time, zmq, random, json, uuid

from threading import RLock, Thread
from dataclasses import asdict

from role import Role
from appenEntity import AppendEntity

HOST = "tcp://127.0.0.1:"
WAIT_TIME_TO_CONNECT_PEERS = 1

from raftLog import RaftLog

from enum import Enum


class MessageType(Enum):
    Leader = 'leader_message'
    Follower = "follower_reply"
    Correction = 'correction'
    HeatBeat = 'heartbeat'


class ElectionNode(RaftLog):
    def __init__(self, internal_port, index, sibling_nodes):
        super().__init__()

        self.internal_port = internal_port
        self.sibling_nodes = sibling_nodes

        self.role = Role.FOLLOWER
        self.leader = None
        self.vote = 0

        self.index = index  # server index
        self.term = -1  # term of the election

        self.voted_for = None  # voted for in current term
        self.committed_index = -1
        self.last_heartbeat = get_time_millis()
        self.timeout = init_get_timeout()
        self.total_nodes = len(self.sibling_nodes) + 1

        self.context = zmq.Context()

        """
        For internal router
        """
        self.reentrant_lock = RLock()

        self.internal_socket = self.context.socket(zmq.ROUTER)
        self.internal_socket.setsockopt(zmq.IDENTITY, f"{self.internal_port}".encode())
        self.internal_socket.bind(f"{HOST}{internal_port}")
        # print("Internal: blinding", HOST, internal_port)

        # listen to sibling_nodes
        internalFollower = Thread(target=self.listenToInternal)
        internalFollower.start()
        time.sleep(WAIT_TIME_TO_CONNECT_PEERS)

        # connect to peers
        internalConnection = Thread(target=self.connectToInernal)
        internalConnection.start()

        # check heartbeat
        heartbeatCheck = Thread(target=self.checkHeartbeat)
        heartbeatCheck.start()

    def connectToInernal(self):
        for port in self.sibling_nodes:
            self.internal_socket.connect(f"{HOST}{port}")
            # print(f"Internal: connecting to {HOST}{port}")
        # give time to actually connect
        time.sleep(WAIT_TIME_TO_CONNECT_PEERS)

    def listenToInternal(self):
        # print(f"Internal: Sever {self.index} at {self.internal_port} start listening to sibling_nodes")
        while True:
            try:
                # print(f"{self.internal_port} trying to recv...")
                sender_id, sender_message = self.internal_socket.recv_multipart()
                message = json.loads(sender_message.decode())
                # print(f"Internal: Server at {self.internal_port} received internal message {message}")
                self.response_to_internal_messages(message)
                # time.sleep(0.01)
            except KeyboardInterrupt:
                self.internal_socket.close()
                self.context.term()

    def checkLogMatch(self, prevLogIndex, prevLogTerm):
        return prevLogIndex == self.get_last_log_index() \
               and prevLogTerm == self.get_last_log_term()

    def response_to_internal_messages(self, message):
        if 'candidateId' in message:
            self.vote_leader(message)
        elif 'vote' in message:
            if message['vote']:
                self.vote += 1
            elif message['term'] > self.term:
                print(f"Internal: Sever {self.index} at {self.internal_port} update to follower")
                self.update_term_return_to_follower(message['term'])

            if self.vote > self.total_nodes // 2 and self.role == Role.CANDIDATE:
                self.transition_to_new_role(Role.LEADER)
                timeArray = time.localtime(time.time())
                otherStyleTime = time.strftime("%H:%M:%S", timeArray)
                print(
                    f"Internal: Server {self.index}  set as Leader with {self.vote} votes at {otherStyleTime}")
                self.vote = 0

        elif 'type' in message:
            if message['type'] == MessageType.HeatBeat.value:
                # print(f"Server {self.index} receive heartbeat")
                self.vote = 0
                term = message['term']
                leader_id = message['leaderId']
                self.reset_last_heartbeat()
                self.leader = leader_id
                self.update_term_return_to_follower(term)

            elif message['type'] == MessageType.Leader.value:
                # print(f"Logs: Server {self.index} received client message {message}")
                message['type'] = MessageType.Follower.value

                # 1. Reply false if term < currentTerm
                if message['term'] < self.term:
                    print(
                        f"Error: Server {self.index} have a higher term {self.term} than {message['term']}, server role: {self.role.value}")
                    if self.role == Role.LEADER and self.checkLogMatch(message['prevLogIndex'], message[
                        'prevLogTerm']):
                        # send this again
                        message['term'] = self.term
                        message['leaderId'] = self.index
                        message['leaderPort'] = self.internal_port
                        print("new leader send this again", message)
                        entry = json.loads(message['entry'])
                        self.create_new_log(
                            entityId=message['entityId'],
                            message=entry,
                            term=self.term)
                        self.send_followers_client_request(entry, message['entityId'])
                    else:
                        message['term'] = self.term
                        self.send_to_peer(message['leaderPort'], json.dumps(message))

                # 2. Reply false if log doesn’t contain an entry at prevLogIndex
                # whose term matches prevLogTerm
                elif not self.checkLogMatch(message['prevLogIndex'], message[
                    'prevLogTerm']):
                    print(
                        f"LogNeedsCorrection: Server {self.index} does not match: prevLogIndex: {message['prevLogIndex']} vs {self.get_last_log_index()}, prevLogTerm: {message['prevLogTerm']} vs {self.get_last_log_term()}")
                    self.send_to_peer(message['leaderPort'], json.dumps(message))

                # 3. commit the message
                elif message['leaderCommit']:
                    # print(f"Commit: Server {self.index} commit {message['entry']}")
                    self.manage_commit_log(message['entry'], message['term'])
                    self.reset_last_heartbeat()
                else:
                    # agree on the message
                    # print(f"Agree: Server {self.index} agree and send back to {message['leaderPort']}")
                    message['agree'] = True
                    self.send_to_peer(message['leaderPort'], json.dumps(message))
                    self.reset_last_heartbeat()

            elif self.role == Role.LEADER and message['type'] == MessageType.Follower.value:
                # hear reply from follower
                # print(f"Logs: Leader {self.index} received {message['agree']} from {message['recipientPort']}")
                if message['agree']:
                    log_id = int(message['entityId'])
                    if log_id not in self.transaction_log:
                        # print("log_id not in self.transaction_log")
                        return

                    self.transaction_log[log_id].agreeCounter += 1
                    # print(f"Agreement: {log_id}, {self.transaction_log[log_id].agreeCounter}")
                    if self.transaction_log[log_id].agreeCounter > self.total_nodes // 2:
                        # more than half agrees on the log
                        # print(f"Logs: Leader {self.index} commit message {message}")

                        # commit the log
                        commit_log = self.transaction_log.pop(log_id)
                        self.logs.append(commit_log)
                        # print(f"{self.internal_port} logs up til now: {self.logs}")

                        #  send to followers
                        message['type'] = MessageType.Leader.value
                        message['term'] = self.term
                        message['leaderCommit'] = True
                        # print(f"broadcast {message}")
                        self.broadcast_dict_to_peers(message)

                        # response to client
                        self.client_messages_state[log_id] = True
                        return True
                else:
                    # follower disagree
                    # 1. higher term
                    if message['term'] > self.term:  # received response from node with higher term
                        self.update_term_return_to_follower(message['term'])
                        return

                    # 2. send previous log
                    # this log: prev log
                    # prev log: the one before prev log
                    message['type'] = MessageType.Correction.value

                    this_log_index = message['prevLogIndex']
                    prev_log_index = this_log_index - 1
                    if prev_log_index < -1:
                        return

                    message['term'] = self.get_pre_log_term(this_log_index)
                    message['prevLogIndex'] = prev_log_index
                    message['prevLogTerm'] = self.get_pre_log_term(prev_log_index)
                    print("correction message", message)
                    self.send_to_peer(message['recipientPort'], json.dumps(message))
            elif message['type'] == MessageType.Correction.value:
                # follower
                if self.role == Role.FOLLOWER:
                    # if this is for previous log correction
                    if message['prevLogIndex'] < self.log_size:
                        # check if that log match
                        # check entry and term
                        if self.get_pre_log_term(message['prevLogIndex']) != message['prevLogTerm']:
                            self.send_to_peer(message['leaderPort'], json.dumps(message))
                            return

                        # find fix
                        # delete the one after previous one
                        self.logs = self.logs[:message['prevLogIndex'] + 1]
                        # add the new one
                        print("add the new one", message, message['entry'], message['term'])
                        self.manage_commit_log(message['entry'], message['term'])
                        self.send_to_peer(message['leaderPort'], json.dumps(message))
                        message['agree'] = True
                        return

                # leader
                elif self.role == Role.LEADER:
                    if message['agree']:
                        # send the next one
                        # this log: prev log
                        # prev log: the one before prev log
                        this_log_index = message['prevLogIndex'] + 1
                        prev_log_index = message['prevLogIndex']
                        # for the last log
                        if this_log_index >= self.log_size:
                            return
                    else:
                        # send previous
                        # this log: prev log
                        # prev log: the one before prev log
                        this_log_index = message['prevLogIndex']
                        prev_log_index = this_log_index - 1
                        if prev_log_index < -1:
                            return

                    message['term'] = self.get_pre_log_term(this_log_index)  # self.logs[this_log_index].term
                    message['entry'] = self.logs[this_log_index].message

                    message['prevLogIndex'] = prev_log_index
                    message['prevLogTerm'] = self.get_pre_log_term(prev_log_index)  # self.logs[prev_log_index].term
                    self.send_to_peer(message['recipientPort'], json.dumps(message))

    """
    communication between peers
    """

    def send_appendEntries(self, message, recipintPort, type, entityId):
        # entityId = int(uuid.uuid4())
        entity = AppendEntity(term=self.term,
                              leaderId=self.index,
                              leaderPort=self.internal_port,
                              prevLogIndex=self.get_last_log_index(),
                              prevLogTerm=self.get_last_log_term(),
                              entry=message,
                              leaderCommit=False,
                              recipientPort=recipintPort,
                              agree=False,
                              entityId=entityId,
                              type=type
                              )

        if type == MessageType.Leader.value:
            self.create_new_log(entityId, message, self.term)

        self.broadcast_dict_to_peers(asdict(entity))

    def broadcast_dict_to_peers(self, message_dict):
        self.broadcast_to_peers(json.dumps(message_dict))

    def broadcast_to_peers(self, message):
        for peer_id in self.sibling_nodes:
            self.send_to_peer(peer_id, message)
        # print(self.internal_port, "sent all messages")

    def send_to_peer(self, peer_id, message):
        self.reentrant_lock.acquire()
        # print(self.internal_port, f'sending "{message}" to', peer_id)
        self.internal_socket.send_multipart([f"{peer_id}".encode(), message.encode()])
        self.reentrant_lock.release()

    """
    Client Messages
    """

    def send_followers_client_request(self, message, messageId):
        for peer_port in self.sibling_nodes:
            self.send_appendEntries(message=json.dumps(message),
                                    recipintPort=peer_port,
                                    type=MessageType.Leader.value,
                                    entityId=messageId)

    """
    HeartBeat
    """

    def checkHeartbeat(self):
        # self.initiate_leader_election()
        while True:
            if self.is_leader():
                # send heartbeat
                for peer_port in self.sibling_nodes:
                    heartBeatId = int(uuid.uuid4())
                    self.send_appendEntries(message="",
                                            recipintPort=peer_port,
                                            type=MessageType.HeatBeat.value,
                                            entityId=heartBeatId)
                    # heartbeatSender = Thread(target=self.broadcastHeartBeat, args=(peer_port,))
                    # heartbeatSender.start()

            if self.check_heartbeat_timeout():
                # time.sleep(0.1)
                self.initiate_leader_election()
            time.sleep(0.1)

    """
    For election
    """

    def increment_term(self):
        self.term += 1
        return

    def transition_to_new_role(self, role):
        self.role = role
        return

    def is_leader(self):
        return self.role == Role.LEADER

    # followers check for timeout
    def check_heartbeat_timeout(self):
        # If leader itself, no need to check heartbeat timeout
        if self.is_leader():
            return False

        cur_time = get_time_millis()
        time_elapsed = cur_time - self.last_heartbeat
        if time_elapsed >= self.timeout:
            # print(f'Server {self.index} at {self.internal_port} heartbeat timeout!'
            #       f'Time elapsed since last heartbeat received: {time_elapsed}.')
            self.reset_last_heartbeat()
            return True
        return False

    # set last_heartbeat as current time, and reset random timeout
    def reset_last_heartbeat(self):
        self.last_heartbeat = get_time_millis()
        self.timeout = get_timeout()
        # print(f"Server {self.index} reset last heartbeat")

    def update_term_return_to_follower(self, term):
        self.reset_last_heartbeat()
        self.term = term
        if self.role != Role.FOLLOWER:
            self.transition_to_new_role(Role.FOLLOWER)
            # print(f'Received response from a higher term node. Returning to follower state.')
        return

    def initiate_leader_election(self):
        # print(f'Server {self.index} at {self.internal_port} initiating leader election...')
        self.vote = 1  # vote for itself

        # change to candidate role
        self.transition_to_new_role(Role.CANDIDATE)
        self.increment_term()
        self.voted_for = None

        data = {
            'term': self.term,
            'candidateId': self.index,
            'internal_port': self.internal_port
        }

        self.broadcast_dict_to_peers(data)

        # a timeout for election
        # electionTimeout = Thread(target=self.countdown)
        # electionTimeout.start()

        # special case: 1 node system
        if self.vote > self.total_nodes / 2 and self.role == Role.CANDIDATE:
            self.transition_to_new_role(Role.LEADER)
        elif self.total_nodes == 1:
            self.transition_to_new_role(Role.FOLLOWER)
        return

    def vote_leader(self, message):
        requester_term = message['term']
        candidate_id = message['candidateId']
        send_port = message['internal_port']

        # found current leader
        if self.term == requester_term and self.is_leader():
            output = {'vote': False, 'term': self.term}
            self.send_to_peer(send_port, json.dumps(output))
            return

        # update term and move to follower state
        if requester_term > self.term:
            self.update_term_return_to_follower(requester_term)
            self.voted_for = candidate_id
            output = {'vote': True, 'term': self.term}
            self.send_to_peer(send_port, json.dumps(output))
            return

        elif requester_term == self.term and (not self.voted_for or self.voted_for == candidate_id):
            self.update_term_return_to_follower(requester_term)
            self.voted_for = candidate_id
            output = {'vote': True, 'term': self.term}
            self.send_to_peer(send_port, json.dumps(output))
            return

        # vote no
        output = {'vote': False, 'term': self.term}
        self.send_to_peer(send_port, json.dumps(output))
        return


# get a random time for timeout
def get_timeout():
    return random.uniform(600, 2000)


def init_get_timeout():
    return random.uniform(50, 1000)


def get_time_millis():
    return time.time() * 1000


def get_uuid():
    return str(uuid.uuid4())


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

    node = ElectionNode(internal_port, node_id, sibling_nodes)
