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

class AlarmMessage(PubSubMessage):
    pubFreq: float
    type: str
    sensor_id: str
    triggered: int
    minRange: float
    maxRange: float
    hz: int

SIMULATED_PROPS = {
    "triggered",
    "minRange",
    "maxRange",
    "hz",
}

class AreaAlarmNode(Node):
    def __init__(self, sensor_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = None
        self.sensor_id = sensor_id
        self.triggered = False
        self.minRange = 1.0
        self.maxRange = 10.0
        self.hz = 3000.0
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="areaalarm",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for sensor.alarm.areaalarm
        self.publisher = self.create_publisher(
            topic=f"sensor.alarm.areaalarm.{self.sensor_id}",
            msg_type=AlarmMessage,
        )

    def simulate_areaalarm(self, name: str):
        """
        Simulate dynamic behavior for 'AreaAlarm' actor.
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

    def get_property_value(self, name):
        if name in SIMULATED_PROPS:
            val = self.simulate_areaalarm(name)
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
        print(f"[{self.__class__.__name__}] Running with id={self.sensor_id}")
        rate = Rate(self.pub_freq)
        while True:
            # DEBUG: topic_base = sensor.alarm.areaalarm
            # DEBUG: endpoint = Publisher, topic = sensor.rangefinder.sonar
            # DEBUG: endpoint = Publisher, topic = sensor.rangefinder.ir
            # DEBUG: endpoint = Publisher, topic = sensor.lidar
            # DEBUG: endpoint = Publisher, topic = sensor.reader.camera
            # DEBUG: endpoint = Publisher, topic = sensor.reader.rfid
            # DEBUG: endpoint = Publisher, topic = sensor.alarm.areaalarm
            # DEBUG: endpoint = Publisher, topic = sensor.alarm.linearalarm
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
            msg = AlarmMessage(
                pubFreq=self.pub_freq,
                sensor_id=self.sensor_id,
                type="AlarmData",
                triggered=int(self.get_property_value("triggered")),
                minRange=float(self.get_property_value("minRange")),
                maxRange=float(self.get_property_value("maxRange")),
                hz=int(self.get_property_value("hz")),
            )
            print(f"[AreaAlarmNode] Publishing to sensor.alarm.areaalarm.{self.sensor_id}: {msg.model_dump()}")
            self.publisher.publish(msg)
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.areaalarm name
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
        sensor_id = sys.argv[1] if len(sys.argv) > 1 else "areaalarm_1"
        node = AreaAlarmNode(sensor_id=sensor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[AreaAlarm] Stopped by user.")
        node.stop()