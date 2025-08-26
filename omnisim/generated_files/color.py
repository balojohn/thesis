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

class ColorMessage(PubSubMessage):
    pubFreq: float
    actor_id: str
    r: int
    g: int
    b: int

SIMULATED_PROPS = {
    "r",
    "g",
    "b",
}

class ColorNode(Node):
    def __init__(self, actor_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = None
        self.actor_id = actor_id
        self.r = 0
        self.g = 0
        self.b = 0
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="color",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for actor.color
        self.publisher = self.create_publisher(
            topic=f"actor.color.{self.actor_id}",
            msg_type=ColorMessage,
        )

    def simulate_color(self, name: str):
        """
        Simulate dynamic behavior for 'Color' actor.
        """
        t = time.time()

        # Default fallback
        if hasattr(self, name):
            base = getattr(self, name)
            if name in {"r", "g", "b"}:
                return max(0, min(255, int(random.gauss(base, 30.0))))
            if isinstance(base, (int, float)):
                return random.gauss(base, 1.0)
            elif isinstance(base, str):
                # Example: rotate dynamic messages
                choices = ["Hello", "World", "Barcode", "Active", "Scan"]
                return random.choice(choices)

    def get_property_value(self, name):
        if name in SIMULATED_PROPS:
            val = self.simulate_color(name)
            if isinstance(val, (int, float)):
                if name in {"r", "g", "b"}:
                    return max(0, min(255, int(val)))
                if name == "age":
                return max(0, int(val))  # convert float to int safely
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
            # DEBUG: topic_base = actor.color
            # DEBUG: endpoint = Publisher, topic = sensor.rangefinder.sonar
            # DEBUG: endpoint = Publisher, topic = actuator.button
            # DEBUG: endpoint = Publisher, topic = actor.envactor.fire
            # DEBUG: endpoint = Publisher, topic = actor.envactor.water
            # DEBUG: endpoint = Publisher, topic = actor.text.barcode
            # DEBUG: endpoint = Publisher, topic = actor.text.qrcode
            # DEBUG: endpoint = Publisher, topic = actor.text.rfidtag
            # DEBUG: endpoint = Publisher, topic = actor.text.plaintext
            # DEBUG: endpoint = Publisher, topic = actor.soundsource
            # DEBUG: endpoint = Publisher, topic = actor.color
            # DEBUG: endpoint = Publisher, topic = actor.human
            msg = ColorMessage(
                pubFreq=self.pub_freq,
                actor_id=self.actor_id,
                type="ColorData",
                r=self.get_property_value("r"),
                g=self.get_property_value("g"),
                b=self.get_property_value("b"),
            )
            print(f"[ColorNode] Publishing to actor.color.{self.actor_id}: {msg.model_dump()}")
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
        actor_id = sys.argv[1] if len(sys.argv) > 1 else "color_1"
        node = ColorNode(actor_id=actor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Color] Stopped by user.")
        node.stop()