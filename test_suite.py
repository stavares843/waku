import subprocess
import base64
from urllib.parse import quote
import time
import logging
import sys

try:
    import requests
except ImportError:
    print("Error: 'requests' module not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('waku_test.log')
    ]
)
logger = logging.getLogger(__name__)


class WakuNodeManager:
    def __init__(self):
        self.base_url = "http://127.0.0.1:21161"
        self.base_url_node1 = "http://127.0.0.1:21161"
        self.base_url_node2 = "http://127.0.0.1:21171"
        self.container_name_node1 = "waku_node1"
        self.container_name_node2 = "waku_node2"
        self.test_results = []

    def start_waku_node1(self):
        logger.info("Starting Waku Node 1...")
        try:
            result = subprocess.run([
                "docker", "run", "-d", "--rm",
                "--name", self.container_name_node1,
                "--network", "waku",
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
                "--peer-exchange=true",
                "--discv5-discovery=true",
                "--relay=true"
            ], check=True, capture_output=True, text=True)
            logger.info(f"Waku Node 1 started successfully. Container ID: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Waku Node 1: {e.stderr}")
            return False

    def start_waku_node2(self):
        logger.info("Starting Waku Node 2...")
        try:
            enr_uri = self.get_enr_uri(self.base_url_node1)
            result = subprocess.run([
                "docker", "run", "-d", "--rm",
                "--name", self.container_name_node2,
                "--network", "waku",
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
                "--peer-exchange=true",
                "--discv5-discovery=true",
                "--relay=true",
                f"--discv5-bootstrap-node={enr_uri}"
            ], check=True, capture_output=True, text=True)
            logger.info(f"Waku Node 2 started successfully. Container ID: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start Waku Node 2: {e.stderr}")
            return False

    def stop_waku_node(self, container_name):
        logger.info(f"Stopping container {container_name}...")
        try:
            subprocess.run(["docker", "stop", container_name], 
                         check=True, capture_output=True, text=True)
            logger.info(f"Container {container_name} stopped successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error stopping container {container_name}: {e.stderr}")
        
        try:
            subprocess.run(["docker", "rm", container_name], 
                         check=True, capture_output=True, text=True)
            logger.info(f"Container {container_name} removed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error removing container {container_name}: {e.stderr}")

    def create_docker_network(self):
        logger.info("Creating Docker network...")
        check_network_cmd = subprocess.run(
            ["docker", "network", "inspect", "waku"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        if check_network_cmd.returncode != 0:
            try:
                # Try with the original subnet first
                result = subprocess.run([
                    "docker", "network", "create", "--driver", "bridge",
                    "--subnet", "172.18.0.0/16", "--gateway", "172.18.0.1", "waku"
                ], capture_output=True, text=True)
                
                if result.returncode != 0 and "overlaps" in result.stderr:
                    # If subnet overlaps, create without explicit subnet and let Docker choose
                    logger.warning("Subnet overlap detected, creating network with auto-assigned subnet...")
                    subprocess.run([
                        "docker", "network", "create", "waku"
                    ], check=True, capture_output=True, text=True)
                elif result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
                
                logger.info("Docker network created successfully")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create Docker network: {e.stderr}")
                return False
        else:
            logger.info("Docker network already exists")
            return True

    def delete_docker_network(self):
        logger.info("Deleting Docker network...")
        try:
            subprocess.run(["docker", "network", "rm", "waku"], 
                         check=True, capture_output=True, text=True)
            logger.info("Docker network deleted successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error deleting Docker network: {e.stderr}")
            return False

    def subscribe_to_topic(self, topic, base_url):
        logger.info(f"Subscribing to topic {topic} on {base_url}...")
        headers = {
            "content-type": "application/json",
            "accept": "text/plain"
        }
        data = [topic]
        try:
            response = requests.post(
                f"{base_url}/relay/v1/auto/subscriptions", 
                headers=headers, 
                json=data,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"Successfully subscribed to topic. Response: {response.text}")
            self.test_results.append(("Subscribe to topic", True, response.text))
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to subscribe to topic: {e}")
            self.test_results.append(("Subscribe to topic", False, str(e)))
            return False

    def publish_message(self, payload, topic, base_url):
        logger.info(f"Publishing message to topic {topic} on {base_url}...")
        headers = {
            "content-type": "application/json"
        }
        message_data = {
            "payload": base64.b64encode(payload.encode()).decode(),
            "contentTopic": topic,
            "timestamp": 0
        }
        try:
            response = requests.post(
                f"{base_url}/relay/v1/auto/messages", 
                headers=headers, 
                json=message_data,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"Message published successfully. Response: {response.text}")
            self.test_results.append(("Publish message", True, response.text))
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to publish message: {e}")
            self.test_results.append(("Publish message", False, str(e)))
            return False

    def confirm_message_publication(self, topic, base_url):
        logger.info(f"Confirming message publication for topic {topic} on {base_url}...")
        encoded_topic = quote(topic, safe='')
        try:
            response = requests.get(
                f"{base_url}/relay/v1/auto/messages/{encoded_topic}",
                timeout=10
            )
            response.raise_for_status()
            messages = response.json()
            message_count = len(messages) if isinstance(messages, list) else 0
            logger.info(f"Message confirmation successful. Found {message_count} messages: {response.text}")
            self.test_results.append(("Confirm message", True, f"{message_count} messages"))
            return True, message_count
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to confirm message: {e}")
            self.test_results.append(("Confirm message", False, str(e)))
            return False, 0

    def get_peers_info(self, base_url):
        logger.info(f"Fetching peers information from {base_url}...")
        try:
            response = requests.get(f"{base_url}/admin/v1/peers", timeout=10)
            response.raise_for_status()
            peers = response.json()
            peer_count = len(peers) if isinstance(peers, list) else 0
            logger.info(f"Peers information retrieved successfully. Found {peer_count} peers: {response.text}")
            self.test_results.append(("Get peers info", True, f"{peer_count} peers"))
            return True, peers
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get peers info: {e}")
            self.test_results.append(("Get peers info", False, str(e)))
            return False, []

    def get_enr_uri(self, base_url):
        logger.info(f"Fetching ENR URI from {base_url}...")
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{base_url}/debug/v1/info", timeout=10)
                response.raise_for_status()
                data = response.json()
                enr_uri = data.get("enrUri")
                if enr_uri:
                    logger.info(f"ENR URI retrieved: {enr_uri}")
                    time.sleep(5)  # Wait for node to be fully ready
                    return enr_uri
                else:
                    logger.warning("ENR URI not found in response")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    logger.error("Failed to retrieve ENR URI after all retries")
                    raise
        return None
    
    def wait_for_node_ready(self, base_url, max_wait=30):
        """Wait for node to be ready by checking the info endpoint"""
        logger.info(f"Waiting for node at {base_url} to be ready...")
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(f"{base_url}/debug/v1/info", timeout=5)
                if response.status_code == 200:
                    logger.info(f"Node at {base_url} is ready")
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(2)
        logger.error(f"Node at {base_url} failed to become ready within {max_wait} seconds")
        return False
    
    def print_test_summary(self):
        """Print a summary of all test results"""
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        passed = sum(1 for _, success, _ in self.test_results if success)
        failed = len(self.test_results) - passed
        
        for test_name, success, details in self.test_results:
            status = "✓ PASS" if success else "✗ FAIL"
            logger.info(f"{status} - {test_name}: {details}")
        
        logger.info("="*60)
        logger.info(f"Total Tests: {len(self.test_results)}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info("="*60 + "\n")
        
        return passed, failed

def main():
    manager = WakuNodeManager()
    test_topic = "/my-app/2/chatroom-1/proto"
    
    try:
        logger.info("Starting Waku Node Test Suite")
        logger.info("="*60)
        
        # Create Docker network
        if not manager.create_docker_network():
            logger.error("Failed to create Docker network. Exiting.")
            return 1

        # Start the first node
        if not manager.start_waku_node1():
            logger.error("Failed to start Waku Node 1. Exiting.")
            return 1
        
        # Wait for node 1 to be ready
        if not manager.wait_for_node_ready(manager.base_url_node1):
            logger.error("Node 1 did not become ready. Exiting.")
            manager.stop_waku_node(manager.container_name_node1)
            return 1

        # Subscribe to a topic on the first node
        manager.subscribe_to_topic(test_topic, manager.base_url_node1)

        # Publish a message from the first node
        manager.publish_message("Test Message from Node 1", test_topic, manager.base_url_node1)
        time.sleep(2)  # Wait for message propagation

        # Confirm message publication on the first node
        success, count = manager.confirm_message_publication(test_topic, manager.base_url_node1)
        if success and count > 0:
            logger.info(f"✓ Successfully confirmed {count} message(s) on Node 1")
        else:
            logger.warning("⚠ No messages found on Node 1")

        # Start the second node
        if not manager.start_waku_node2():
            logger.error("Failed to start Waku Node 2. Continuing with cleanup.")
        else:
            # Wait for node 2 to be ready
            if manager.wait_for_node_ready(manager.base_url_node2):
                time.sleep(5)  # Additional wait for peer discovery
                
                # Subscribe to the same topic on the second node
                manager.subscribe_to_topic(test_topic, manager.base_url_node2)
                
                # Publish a message from the second node
                manager.publish_message("Test Message from Node 2", test_topic, manager.base_url_node2)
                time.sleep(2)

                # Confirm message publication on the second node
                success, count = manager.confirm_message_publication(test_topic, manager.base_url_node2)
                if success and count > 0:
                    logger.info(f"✓ Successfully confirmed {count} message(s) on Node 2")

                # Check peers information on both nodes
                success1, peers1 = manager.get_peers_info(manager.base_url_node1)
                if success1:
                    logger.info(f"Node 1 has {len(peers1)} peer(s)")
                
                success2, peers2 = manager.get_peers_info(manager.base_url_node2)
                if success2:
                    logger.info(f"Node 2 has {len(peers2)} peer(s)")

                # Verify peer connection
                if success1 and len(peers1) > 0 and success2 and len(peers2) > 0:
                    logger.info("✓ Nodes successfully connected to each other")
                    manager.test_results.append(("Peer connection", True, "Nodes connected"))
                else:
                    logger.warning("⚠ Nodes may not be connected")
                    manager.test_results.append(("Peer connection", False, "No peers found"))

                # Stop the second node
                manager.stop_waku_node(manager.container_name_node2)

        # Stop the first node
        manager.stop_waku_node(manager.container_name_node1)

        # Delete Docker network
        manager.delete_docker_network()
        
        # Print test summary
        _, failed = manager.print_test_summary()
        
        logger.info("Waku Node Test Suite completed")
        return 0 if failed == 0 else 1
        
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user")
        manager.stop_waku_node(manager.container_name_node1)
        manager.stop_waku_node(manager.container_name_node2)
        manager.delete_docker_network()
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        manager.stop_waku_node(manager.container_name_node1)
        manager.stop_waku_node(manager.container_name_node2)
        manager.delete_docker_network()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
