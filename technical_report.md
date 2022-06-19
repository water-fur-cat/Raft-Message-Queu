# Technical Report

# Part 1 - Message Queue
## Implementation
* In general, the messages are stored in an in-memory dictionary data structure, with keys representing different topics. When the server node receive a request from the client, it responds according to the type and the method in the request.

* Besides, checks are added to ensure that the required keys, such as type, method, topic, and message, are present in the request before accessing the data of the key.


### Topic
* The topic endpoint is used to both create and retrieve a list of topics.
* The topic name is a key in the message queue dictionary for each topic, and the data for each topic is stored in an array.

#### PUT /topic: 
Create a new topic.
* Implementation: if the topic already exists in the message queue dictionary, return ```False```; otherwise, the topic name is added to the dictionary as the key of an empty array.
* Request: ```{'topic': str, "type": "topic", "method": "PUT"}```
* Returns: ```{'success': bool}```
  * ```True``` if the topic was created.
  * ```False``` if the topic already exists or was not created for another reason.

#### GET /topic
Get a list of topics.
* Implementation: returns a list of keys (representing the topic names) in the message queue dictionary.
* Request: ```{'topic': str, "type": "topic", "method": "GET"}```
* Returns: ```{'success': bool, 'topics': [str]}```
  * Returns with a list of topics in the message queue. 
  * If there are no topics it returns an empty list.


### Message
* The message endpoint is used for adding a message to a topic and getting a message from a topic.
* When putting message to the topic, the new message is appended to the specific array; when getting message, the first message from that array is popped out.

#### PUT /message
Put a new message to a topic.
* Implementation: If the topic exists, the new message is appended to the specific topic array, and returns ```True```; otherwise, returns ```False```.
* Request: ```{"type": "message", "method": "PUT", "topic": str, "message": str}```
* Returns: ```{'success' : bool}```
  * ```True``` if the message is added to the topic.
  * ```False``` if the topic does not exist or was not created for another reason.

#### GET /message
Get a message from a topic.
* Implementation: returns a message from the topic.
* Request: ```{"type": "message", "method": "GET", "topic": str}```
* Returns: ```Returns:{'success' : bool, 'message': str}```
  * Returns the message if the topic exists and there is at least one message in the topic
  * Returns ```{'success' : False}``` if the topic does not exist or there are no messages in the topic


## Possible Shortcoming
* Since the messages in the message queue are stored in a dictionary, the data will be lost if the system is shut down. A better way may be using a database to store the data.

# Part 2 - Election

## Implementation
- Each node starts as a ```Follower```. Each node has a timer with timeout value picked randomly from uniform distribution from 600 to 2000 milliseconds(initial with timeout value picked randomly from uniform distribution from 50 to 1000). When node timers time out, it starts election process.
- After starting election process, The ```Follower node``` moves to ```Candidate role``` and increases current term. It sends a ```voteRequest``` to each node in the list. The node votes for itself and collects the votes from others. 
- Each follower will only vote for one candidate per term. In an election, each server node will cast at most one vote for one term number. For example, node C, whose term number is 3, first receives a voting request from node A containing term number 4, and then receives a voting request from node B containing term number 4. Then node C will cast the only vote to node A. When node C receives voting message from node B later, it has no more votes to cast for the term numbered 4.
- Followers with high log integrity (that is, the term number corresponding to the last log entry has a larger value and a larger index number) refuse to vote for candidates with low log integrity. For example, the term number of node B is 3, the term number of node C is 4, the term number corresponding to the last log entry of node B is 3, and node C is 2, then when node C requests node B to vote for itself, the node B will decline to vote.
- If a ```Candidate node``` receives votes from the majority of nodes, it moves to ```Leader state```. At most one leader can be elected for each term.
- If two or more candidates run for election at the same time, neither will receive a majority of votes. Without the majority after some time, determined with a separate randomized timeout, they are reset back to followers and subject to randomized election timeouts again. This should result in a single follower becoming candidate first, which allows a single leader to be elected.
- During election process, if the node discovers the current leader or any node with term greater than its term value, it moves back to ```Follower state```.
- A ```Leader``` must have most up-to-date logs, namely the longest log.
- If the role of a node is ```Leader```, it will send heartbeat requests to every node in the list every amount of time.
- When a node receives a heartbeat request with a term greater than or equal to its own, it updates its counting down timer.
- Router is used for internal communication.

## Possible Shortcoming
- If more than half of the nodes in the list fail, it is likely that no leader will be elected because the total number of nodes is hardcoded.


# Part 3 - Replication

## Implementation
- When receiving message (except checking status request) from a client:
  - If the node is the ```Leader```: 
    - It will send the request in an ```appendEntry``` to all other nodes in the network, and stores a pending log in ```transaction log```.
    - When the majority of the nodes agree on the ```appendEntry```, the leader will:
      1. Mark this appendEntry request as ```commit```, and send a committed appendEntry request to all nodes in the network.
      2. Commit the specific log in the ```transaction logs```, pops it out, and add it to ```logs```.
      3. Execute the client request, and reply to the client.
  - Otherwise, the node returns ```{'success': False}``` 

* When a node receives a message from internal nodes (except heartbeat messages):
  * If the node is a ```Leader```:
    * If the type of the message is ```"follower_reply"```:
      * If the follower replies ```agree``` on the appendEntry, the leader add one to the ```agree counter``` of the corresponding pending log. If the log is not pending anymore, namely the log is committed, the leader just ignore this message.
      * Otherwise, 
        1. If the term in the message is greater than the node's term, it will update its term and switch to a follower role.
        2. If the term is not higher, it is possible that the log of the follower node differs from that of the leader node. As a result, the leader will send a correction message to that follower to begin the process of finding the last index of logs on which both nodes agree.

    * If the type of the message is ```'correction'```, this indicates that the leader is checking and attempting to correct the follower's log.
      1. If the follower agrees on that message, it means that the last index of logs on which both nodes agree has been discovered, and the leader will begin to send the log following that index in the ```appendEntry``` to the follower.
      2. Otherwise, the leader sends the log preceding that index in the ```appendEntry``` to that follower to see whether the previous log matches.
    
    * If the type of the message is ```'leader_message'```, this means that somehow the old leader's message finally arrives, but the system has elected a new node. If the previous index and term match, the new leader sends the message to all nodes again, ensuring that the client's request is not discarded.
  
  * If the node is a Follower:
    * If the type of the message is ```'leader_message'```:
      1. If the term in the message is smaller than the node's term, it attaches its term to the message and replies disagree to the sender.
      2. If the previous log does not match, it replies disagree to the sender.
      3. If the message is a commit message, it executes the request included in the message by the client, and adds a commit log to its own logs.
      4. Otherwise, it replies agree to the leader.
    * If the type of the message is ```'correction'```:
      1. If the log from the message matches the log at the index, the node deletes everything after that index and appends the "new" entry log. Then it sends an agree message back to the leader.
      2. Otherwise, it replies disagree to the sender.

## Possible Shortcoming
* The client's request may occasionally receive ```{"success": False}```, because the system elected a new leader during the time the client was got to know the previous leader and attempted to send a request to get/put topics or get/put messages.



## reference
- https://github.com/makslevental/raft_demo_mpcs2022/blob/main/zmq_comms.py
- https://raft.github.io/raft.pdf