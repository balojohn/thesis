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



def start_redis():
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

class SonarRangeMessage(PubSubMessage):
    pubFreq: float
    type: str
    sensor_id: str

class SonarNode(Node):
    def __init__(self, sensor_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.sensor_id = sensor_id
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="sonar",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for sensor.rangefinder.sonar
        self.publisher = self.create_publisher(
            topic=f"sensor.rangefinder.sonar.{self.sensor_id}",
            msg_type=SonarRangeMessage,
        )

    def start(self):
        # Start commlib's internal loop in the background (since run() is blocking)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print(f"[{self.__class__.__name__}] Running with id={self.sensor_id}")
        rate = Rate(self.pub_freq)
        while True:
            # create the message
            msg = SonarRangeMessage(
                pubFreq=self.pub_freq,
                sensor_id=self.sensor_id,
                type="RangeData"
            )
            print(f"[SonarNode] Publishing to sensor.rangefinder.sonar.{self.sensor_id}: {msg.model_dump()}")
            self.publisher.publish(msg)
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.sonar sonar_2
if __name__ == '__main__':
    start_redis()
    try:
        try:
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            print("[Redis] Connected successfully.")
        except redis.exceptions.ConnectionError:
            print("[Redis] Not running. Start Redis server first.")
            exit(1)
        sensor_id = sys.argv[1] if len(sys.argv) > 1 else "sonar_1"
        node = SonarNode(sensor_id=sensor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Sonar] Stopped by user.")
        node.stop()