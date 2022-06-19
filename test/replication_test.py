import time

import pytest

from test_utils import Swarm

NUM_NODES_ARRAY = [5]
PROGRAM_FILE_PATH = "../src/node.py"
TEST_TOPIC = "test_topic"
TEST_MESSAGE = "Test Message"

ELECTION_TIMEOUT = 2.0
NUMBER_OF_LOOP_FOR_SEARCHING_LEADER = 3


@pytest.fixture
def swarm(num_nodes):
    swarm = Swarm(PROGRAM_FILE_PATH, num_nodes)
    try:
        swarm.start(ELECTION_TIMEOUT)
        yield swarm
    finally:
        swarm.clean()


def wait_for_commit(seconds=1):
    time.sleep(seconds)


@pytest.mark.parametrize("num_nodes", NUM_NODES_ARRAY)
def test_is_topic_shared(swarm: Swarm, num_nodes: int):
    leader1 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert leader1 is not None
    print("put topic")
    assert leader1.put_topic(TEST_TOPIC) == {"success": True}

    leader1.commit_clean(ELECTION_TIMEOUT)
    leader2 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert leader2 is not None
    print("get topic")
    assert leader2.get_topics() == {"success": True, "topics": [TEST_TOPIC]}


@pytest.mark.parametrize("num_nodes", NUM_NODES_ARRAY)
def test_is_message_shared(swarm: Swarm, num_nodes: int):
    leader1 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert leader1 is not None
    print("put topic")
    assert leader1.put_topic(TEST_TOPIC) == {"success": True}
    assert leader1.put_message(TEST_TOPIC, TEST_MESSAGE) == {"success": True}

    leader1.commit_clean(ELECTION_TIMEOUT)
    leader2 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert leader2 is not None
    print("put message")
    assert leader2.get_message(TEST_TOPIC) == {"success": True, "message": TEST_MESSAGE}


# ADD TESTS
@pytest.mark.parametrize("num_nodes", NUM_NODES_ARRAY)
def test_multi_leaders(swarm: Swarm, num_nodes: int):
    leader1 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert leader1 is not None
    print("put topic")
    assert leader1.put_topic(TEST_TOPIC) == {"success": True}
    assert leader1.put_message(TEST_TOPIC, TEST_MESSAGE) == {"success": True}

    print("kill leader1")
    leader1.commit_clean(ELECTION_TIMEOUT)
    leader2 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert leader2 is not None
    print("put message")
    assert leader2.get_message(TEST_TOPIC) == {"success": True, "message": TEST_MESSAGE}

    print("kill leader2")
    leader2.commit_clean(ELECTION_TIMEOUT)
    leader3 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert leader2 is not None
    print("get topic")
    assert leader3.get_topics() == {"success": True, "topics": [TEST_TOPIC]}
