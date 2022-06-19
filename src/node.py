import sys
import json
from MessageQueue import MessageQueue

HOST = "tcp://127.0.0.1:"
WAIT_TIME_TO_CONNECT_PEERS = 1


class RaftNode(MessageQueue):
    def __init__(self, port, internal_port, index, sibling_nodes):
        super().__init__(port, internal_port, index, sibling_nodes)


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
