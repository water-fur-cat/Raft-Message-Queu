# Testing Report

## Part 1 - Message Queue
1. Test by test provided in [message_queue_test.py](https://github.com/mpcs-52040/2022-project-tests/blob/main/test/message_queue_test.py) to make sure the outputs of get topics, put topics(with and without the same topic), multiple times, put messages (with and without topic created), and get messages(with and without messages in topic).
2. Added some edge cases tests to see if the message queue will still response correctly in [submission_test_message_queue.py](/test/submission_test_message_queue.py)
   * get request without type
   * put request without type
   * request without method but with ```type=topic```
   * request without method but with ```type=message```
   * get message request without topic
   * put message request without topic   
   * put message request without message

#### Possible Shortcoming
We did not test hundreds of thousands of topics and messages for the message queue, so the speed when there are mountains of requests is unknown.


## Part 2 - Election

1. Initial Election
   * Run ```node.py``` and to see the output. 

   * To ensure there was only one leader at a time, I ran ```python -m src.node config.json index``` with index 0 and 1 and 2 and 3(four nodes), and printed out their role and timeout, whether they ran for election, how they voted, and who the current leader was. 

   * Also tested by increasing the timeout windows to see the state and progress of each node and check there was only a single leader in power at a time.

   * If no heartbeat is received within a random amount of time, the node prints out a message reflecting that it starts an election and sends all nodes in the list request for votes. In this situation, the followers compares the term in the request and their own and prints them out. Upon receiving a majority of votes, the elected leader prints out a message stating that it becomes the leader with how many votes, and prints heartbeat messages to the terminal each time it sends a heartbeat to followers.

2. Leader election after failures: 
   * Run ```node.py``` and to see the output.

   * After the initial leader election, I forcibly killed the leader node by Ctrl+c.
   * Then the alive servers no longer receive heartbeats from the original leader, and therefore their election timeouts continue counting down. The first node whose timer expires sends a request for votes. The other servers vote for the candidate. The candidate, upon receiving a majority of votes, turns to be the new leader, and begins sending out heartbeats. I repeated this so that only three nodes remained and ensured one and only one leader was elected after each failure.

   1. leader_election_test.py
   Tests ```vote_leader()``` and ```initiate_leader_election()``` method which triggers the election
   But it has an error so it couldn't be used.


## Part 3 - Replication
1. log_replication_test.py
Tests ```response_to_node()``` method and ```append_entries()``` method called by leader node to send log entries to follower nodes.

2. Run test ```test_is_topic_shared``` in [replication_test.py](https://github.com/mpcs-52040/2022-project-tests/blob/main/test/replication_test.py) and monitor what is printed out in the console to make sure that what messages did the followers receive, how did the message commit, what are in the logs for each node and so on.

4. Test by test provided in [replication_test.py](https://github.com/mpcs-52040/2022-project-tests/blob/main/test/replication_test.py) to make sure the messages are still correct on other servers when the leader is killed.

5. Added new tests in [submission_test_replication.py](/test/submission_test_replication.py)
   * test whether the system works when the leader is killed in the second time
   * test the system with more complex client requests

#### Possible Shortcoming
We did not test hundreds of thousands topics and messages for replication, nor did we test with a large number of server nodes. The speed might slow down in those situations.