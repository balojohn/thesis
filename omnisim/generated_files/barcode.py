import random
import math
import sys
import threading
import subprocess
import time
import redis
# import os
from commlib.msg import PubSubMessage # MessageHeader
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate
from ..utils import Dispersion

# Path to your redis-server executable
REDIS_PATH = r"C:\redis\redis-server.exe"
def redis_start():
    print("[System] Starting Redis server...")
    try:
        proc = subprocess.Popen([REDIS_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)  # give Redis a moment to start
        r = redis.Redis(host='localhost', port=6379)
        if r.ping():
            print("[System] Redis is now running.")
            return proc
    except Exception as e:
        print(f"[ERROR] Could not start Redis: {e}")
        sys.exit(1)

class TextMessage(PubSubMessage):
    pubFreq: float
    actor_id: str
    type: str
    message: str

SIMULATED_PROPS = {
    "message",
}

class BarcodeNode(Node):
    def __init__(self, actor_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = None
        self.actor_id = actor_id
        self.message = "Something"
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="barcode",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for actor.text.barcode
        self.publisher = self.create_publisher(
            topic=f"actor.text.barcode.{self.actor_id}",
            msg_type=TextMessage,
        )

    def simulate_barcode(self, name: str):
        """
        Simulate dynamic behavior for 'Barcode' actor.
        """
        t = time.time()

        # Default fallback
        if hasattr(self, name):
            base = getattr(self, name)
            if isinstance(base, (int, float)):
                return random.gauss(base, 1.0)
            elif isinstance(base, str):
                # Example: rotate dynamic messages
                choices = ["Hello", "World", "Barcode", "Active", "Scan"]
                return random.choice(choices)
        return 0.0

    def get_property_value(self, name):
        if name in SIMULATED_PROPS:
            val = self.simulate_barcode(name)
            if isinstance(val, (int, float)):
                return round(val, 2)
            else:
                return val
        if hasattr(self, name):
            return getattr(self, name)

    def start(self):
        # Start commlib's internal loop in the background (since run() is blocking)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print(f"[{self.__class__.__name__}] Running with id={self.actor_id}")
        rate = Rate(self.pub_freq)
        while True:
            msg = TextMessage(
                pubFreq=self.pub_freq,
                actor_id=self.actor_id,
                type="TextData",
                message=self.get_property_value("message"),
            )
            print(f"[BarcodeNode] Publishing to actor.text.barcode.{self.actor_id}: {msg.model_dump()}")
            self.publisher.publish(msg)
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.sonar sonar_2
if __name__ == '__main__':
    redis_start()
    try:
        try:
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            print("[Redis] Connected successfully.")
        except redis.exceptions.ConnectionError:
            print("[Redis] Not running. Start Redis server first.")
            exit(1)
        actor_id = sys.argv[1] if len(sys.argv) > 1 else "barcode_1"
        node = BarcodeNode(actor_id=actor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Barcode] Stopped by user.")
        node.stop()