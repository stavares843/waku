import subprocess
import requests
import base64
from urllib.parse import quote
import time

class WakuNodeManager:
    def __init__(self):
        self.base_url = "http://127.0.0.1:21161"
        self.base_url_node1 = "http://127.0.0.1:21161"
        self.base_url_node2 = "http://127.0.0.1:21171"
        self.container_name_node1 = "waku_node1"
        self.container_name_node2 = "waku_node2"

    def start_waku_node1(self):
        print("Starting Waku Node 1...")
        # Start the first Waku node
        subprocess.run([
            "docker", "run", "-d", "--rm",
            "--name", self.container_name_node1,
            "--network", "waku",  # Connect to the Docker network
            "-p", "21161:21161",
            "-p", "21162:21162",
            "-p", "21163:21163",
            "-p", "21164:21164",
            "-p", "21165:21165",
            "wakuorg/nwaku:v0.24.0",
            "--listen-address=0.0.0.0",
            "--rest=true",
            "--rest-admin=true",
            "--websocket-support=true",
            "--log-level=TRACE",
            "--rest-relay-cache-capacity=100",
            "--websocket-port=21163",
            "--rest-port=21161",
            "--tcp-port=21162",
            "--discv5-udp-port=21164",
            "--rest-address=0.0.0.0",
            "--nat=extip:172.18.111.226",
            "--peer-exchange=true",
            "--discv5-discovery=true",
            "--relay=true"
        ])
        print("Waku Node 1 started.")

    def start_waku_node2(self):
        print("Starting Waku Node 2...")
        # Start the second Waku node
        subprocess.run([
            "docker", "run", "-d", "--rm",
            "--name", self.container_name_node2,
            "--network", "waku",  # Connect to the Docker network
            "-p", "21171:21161",
            "-p", "21172:21162",
            "-p", "21173:21163",
            "-p", "21174:21164",
            "-p", "21175:21165",
            "wakuorg/nwaku:v0.24.0",
            "--listen-address=0.0.0.0",
            "--rest=true",
            "--rest-admin=true",
            "--websocket-support=true",
            "--log-level=TRACE",
            "--rest-relay-cache-capacity=100",
            "--websocket-port=21163",
            "--rest-port=21161",
            "--tcp-port=21162",
            "--discv5-udp-port=21164",
            "--rest-address=0.0.0.0",
            "--nat=extip:172.18.111.236",  # Different external IP for node 2
            "--peer-exchange=true",
            "--discv5-discovery=true",
            "--relay=true",
            f"--discv5-bootstrap-node={self.get_enr_uri(self.base_url_node1)}"
        ])
        print("Waku Node 2 started.")

    def stop_waku_node(self, container_name):
        print(f"Stopping container {container_name}...")
        # Stop the Waku node
        try:
            subprocess.run(["docker", "stop", container_name], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error stopping container {container_name}: {e}")
        
        # Remove the stopped container
        try:
            subprocess.run(["docker", "rm", container_name], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error removing container {container_name}: {e}")

        # Delete the image
        subprocess.run(["docker", "rmi", "wakuorg/nwaku:v0.24.0"])

    def create_docker_network(self):
        print("Creating Docker network...")
        # Check if network already exists
        check_network_cmd = subprocess.run(["docker", "network", "inspect", "waku"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check_network_cmd.returncode != 0:
            # Create the network if it doesn't exist
            subprocess.run([
                "docker", "network", "create", "--driver", "bridge",
                "--subnet", "172.18.0.0/16", "--gateway", "172.18.0.1", "waku"
            ])
            print("Docker network created.")
        else:
            print("Docker network already exists.")

    def delete_docker_network(self):
        print("Deleting Docker network...")
        # Delete the network
        try:
            subprocess.run(["docker", "network", "rm", "waku"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error deleting Docker network: {e}")
        else:
            print("Docker network deleted.")

    def subscribe_to_topic(self, topic, base_url):
        print(f"Subscribing to topic {topic} on {base_url}...")
        # Subscribe to a topic
        headers = {
            "content-type": "application/json",
            "accept": "text/plain"
        }
        data = [topic]
        response = requests.post(f"{base_url}/relay/v1/auto/subscriptions", headers=headers, json=data)
        print("Subscription response:", response.text)

    def publish_message(self, payload, topic, base_url):
        print(f"Publishing message to topic {topic} on {base_url}...")
        # Publish a message
        headers = {
            "content-type": "application/json"
        }
        payload = {
            "payload": base64.b64encode(payload.encode()).decode(),
            "contentTopic": topic,
            "timestamp": 0
        }
        response = requests.post(f"{base_url}/relay/v1/auto/messages", headers=headers, json=payload)
        print("Publish message response:", response.text)

    def confirm_message_publication(self, topic, base_url):
        print(f"Confirming message publication for topic {topic} on {base_url}...")
        # Confirm message publication
        encoded_topic = quote(topic, safe='')
        response = requests.get(f"{base_url}/relay/v1/auto/messages/{encoded_topic}")
        print("Confirm message publication response:", response.text)

    def get_peers_info(self, base_url):
        print(f"Fetching peers information from {base_url}...")
        # Fetch and print contents of /admin/v1/peers endpoint
        response = requests.get(f"{base_url}/admin/v1/peers")
        print("Peers information:", response.text)

    def get_enr_uri(self, base_url):
        # Fetch and return the ENR URI of a node
        response = requests.get(f"{base_url}/debug/v1/info")
        data = response.json()
        print(data["enrUri"])
        time.sleep(10)
        return data["enrUri"]

def main():
    manager = WakuNodeManager()

    # Create Docker network
    manager.create_docker_network()

    # Start the first node
    manager.start_waku_node1()
    time.sleep(3)  # Adding delay after starting the first node

    # Subscribe to a topic on the first node
    manager.subscribe_to_topic("/my-app/2/chatroom-1/proto", manager.base_url_node1)

    # Publish a message from the first node
    manager.publish_message("Custom Message", "/my-app/2/chatroom-1/proto", manager.base_url_node1)

    # Confirm message publication on the first node
    manager.confirm_message_publication("/my-app/2/chatroom-1/proto", manager.base_url_node1)

    # Start the second node
    manager.start_waku_node2()
    time.sleep(50)  # Adding delay after starting the second node

    # Subscribe to a topic on the second node
    #manager.subscribe_to_topic("/my-app/2/chatroom-1/proto", manager.base_url_node2)

    # Publish a message from the second node
    #manager.publish_message("Another Custom Message", "/my-app/2/chatroom-1/proto", manager.base_url_node2)

    # Confirm message publication on the second node
    #manager.confirm_message_publication("/my-app/2/chatroom-1/proto", manager.base_url_node2)

    # Check peers information on the first node
    manager.get_peers_info(manager.base_url_node1)

    # Check peers information on the second node
    #manager.get_peers_info(manager.base_url_node2)

    # Stop the first node
    manager.stop_waku_node(manager.container_name_node1)

    # Stop the second node
    manager.stop_waku_node(manager.container_name_node2)

    # Delete Docker network
    manager.delete_docker_network()

if __name__ == "__main__":
    main()
