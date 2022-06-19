import pytest

from test_utils import Swarm

TEST_TOPIC = "test_topic"
TEST_MESSAGE = "Test Message"
PROGRAM_FILE_PATH = "../src/node.py"
ELECTION_TIMEOUT = 2.0


@pytest.fixture
def node_with_test_topic():
    node = Swarm(PROGRAM_FILE_PATH, 1)[0]
    try:
        node.start(ELECTION_TIMEOUT)
        node.wait_for_startup()
        assert node.put_topic(TEST_TOPIC) == {"success": True}
        yield node
    finally:
        node.clean()


@pytest.fixture
def node():
    node = Swarm(PROGRAM_FILE_PATH, 1)[0]
    try:
        node.start(ELECTION_TIMEOUT)
        node.wait_for_startup()
        yield node
    finally:
        node.clean()


# Added TOPIC TESTS

# request without type
def test_get_without_type(node):
    assert node.get_without_type() == {"success": False}


def test_post_without_type(node):
    assert node.post_without_type() == {"success": False}


# request without method
def test_topics_without_method(node):
    assert node.topics_without_method() == {"success": False}


# Added MESSAGE TEST
def test_message_without_method(node_with_test_topic):
    assert node_with_test_topic.message_without_method(TEST_TOPIC) == {"success": False}


def test_get_message_without_topic(node_with_test_topic):
    assert node_with_test_topic.get_message_without_topic() == {"success": False}


def test_put_message_without_topic(node_with_test_topic):
    assert node_with_test_topic.put_message_without_topic(TEST_MESSAGE) == {"success": False}


def put_message_without_message(node_with_test_topic):
    assert node_with_test_topic.put_message_without_message(TEST_MESSAGE) == {"success": False}

