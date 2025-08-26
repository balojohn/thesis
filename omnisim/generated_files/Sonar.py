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

class RangeMessage(PubSubMessage):
    pubFreq: float
    type: str
    sensor_id: str
    hfov: float
    vfov: float
    distance: float
    minRange: float
    maxRange: float

SIMULATED_PROPS = {
    "hfov",
    "vfov",
    "distance",
    "minRange",
    "maxRange",
}

class SonarNode(Node):
    def __init__(self, sensor_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = None
        self.sensor_id = sensor_id
        self.hfov = 60.0
        self.vfov = 37.9
        self.distance = 0.0
        self.minRange = 10.0
        self.maxRange = 250.0
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="sonar",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for sensor.rangefinder.sonar
        self.publisher = self.create_publisher(
            topic=f"sensor.rangefinder.sonar.{self.sensor_id}",
            msg_type=RangeMessage,
        )

    def simulate_sonar(self, name: str):
        """
        Simulate dynamic behavior for 'Sonar' actor.
        """
        t = time.time()

        # Simulate range oscillation (Sonar)
        amplitude = (self.maxRange - self.minRange) / 2
        center = (self.maxRange + self.minRange) / 2
        wave = amplitude * math.sin(t)
        base = center + wave
        return max(self.minRange, min(self.maxRange, base))


    def get_property_value(self, name):
        if name in SIMULATED_PROPS:
            val = self.simulate_sonar(name)
            if isinstance(val, (int, float)):
                return round(random.gauss(val, 1.5), 2)
            else:
                return val
        if hasattr(self, name):
            return getattr(self, name)

    def start(self):
        # Start commlib's internal loop in the background (since run() is blocking)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print(f"[{self.__class__.__name__}] Running with id={self.sensor_id}")
        rate = Rate(self.pub_freq)
        while True:
            # DEBUG: topic_base = sensor.rangefinder.sonar
            # DEBUG: endpoint = Publisher, topic = sensor.rangefinder.sonar
            # DEBUG: endpoint = Publisher, topic = sensor.rangefinder.ir
            # DEBUG: endpoint = Publisher, topic = sensor.lidar
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
            msg = RangeMessage(
                pubFreq=self.pub_freq,
                sensor_id=self.sensor_id,
                type="RangeData",
                hfov=self.get_property_value("hfov"),
                vfov=self.get_property_value("vfov"),
                distance=self.get_property_value("distance"),
                minRange=self.get_property_value("minRange"),
                maxRange=self.get_property_value("maxRange"),
            )
            print(f"[SonarNode] Publishing to sensor.rangefinder.sonar.{self.sensor_id}: {msg.model_dump()}")
            self.publisher.publish(msg)
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.sonar name
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
        sensor_id = sys.argv[1] if len(sys.argv) > 1 else "sonar_1"
        node = SonarNode(sensor_id=sensor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Sonar] Stopped by user.")
        node.stop()