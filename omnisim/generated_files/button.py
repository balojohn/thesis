import sys
import threading
import subprocess
import time
import redis
import os
from commlib.msg import MessageHeader, PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate

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

class ButtonMessage(PubSubMessage):
    pubFreq: float
    actuator_id: str
    state: str

class ButtonNode(Node):
    def __init__(self, actuator_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.actuator_id = actuator_id
        self.state = 1

        conn_params = ConnectionParameters()

        super().__init__(
            node_name="button",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for actuator.button
        self.publisher = self.create_publisher(
            topic=f"actuator.singlebutton.button.{self.actuator_id}",
            msg_type=ButtonMessage,
        )

    def simulate_button(self):
        # TODO: implement actual simulation logic for Button
        return 0.0

    def start(self):
        # Start commlib's internal loop in the background (since run() is blocking)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print(f"[{self.__class__.__name__}] Running with id={self.actuator_id}")
        rate = Rate(self.pub_freq)
        while True:
            # create the message
            msg = ButtonMessage(
                pubFreq=self.pub_freq,
                actuator_id=self.actuator_id,
                type="ButtonData",
                state = self.state,
            )
            print(f"[ButtonNode] Publishing to actuator.singlebutton.button.{self.actuator_id}: {msg.model_dump()}")
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
        actuator_id = sys.argv[1] if len(sys.argv) > 1 else "button_1"
        node = ButtonNode(actuator_id=actuator_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Button] Stopped by user.")
        node.stop()