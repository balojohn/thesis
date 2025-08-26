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

class EnvDeviceMessage(PubSubMessage):
    pubFreq: float
    actuator_id: str
    value: float

SIMULATED_PROPS = {
    "value",
}

class HumidifierNode(Node):
    def __init__(self, actuator_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = Dispersion(
            "Quadratic",
            a=1.0,
            b=0.0,
            c=0.0,
        )
        self.actuator_id = actuator_id
        self.value = 0.0
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="humidifier",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for actuator.envdevice.humidifier
        self.publisher = self.create_publisher(
            topic=f"actuator.envdevice.humidifier.{self.actuator_id}",
            msg_type=EnvDeviceMessage,
        )

    def simulate_humidifier(self, name: str):
        """
        Simulate dynamic behavior for 'Humidifier' actor.
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
            val = self.simulate_humidifier(name)
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
        print(f"[{self.__class__.__name__}] Running with id={self.actuator_id}")
        rate = Rate(self.pub_freq)
        while True:
            # DEBUG: topic_base = actuator.envdevice.humidifier
            # DEBUG: endpoint = Publisher, topic = sensor.rangefinder.sonar
            # DEBUG: endpoint = Publisher, topic = sensor.rangefinder.ir
            # DEBUG: endpoint = Publisher, topic = sensor.lidar
            # DEBUG: endpoint = Publisher, topic = sensor.reader.camera
            # DEBUG: endpoint = Publisher, topic = sensor.reader.rfid
            # DEBUG: endpoint = Publisher, topic = sensor.alarm.areaalarm
            # DEBUG: endpoint = Publisher, topic = sensor.alarm.linearalarm
            # DEBUG: endpoint = Publisher, topic = sensor.microphone
            # DEBUG: endpoint = Publisher, topic = sensor.light
            # DEBUG: endpoint = Publisher, topic = actuator.pantilt
            # DEBUG: endpoint = Publisher, topic = actuator.envdevice.thermostat
            # DEBUG: endpoint = Publisher, topic = actuator.envdevice.humidifier
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
            msg = EnvDeviceMessage(
                pubFreq=self.pub_freq,
                actuator_id=self.actuator_id,
                type="EnvDeviceData",
                value=float(self.get_property_value("value")),
            )
            print(f"[HumidifierNode] Publishing to actuator.envdevice.humidifier.{self.actuator_id}: {msg.model_dump()}")
            self.publisher.publish(msg)
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.humidifier name
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
        actuator_id = sys.argv[1] if len(sys.argv) > 1 else "humidifier_1"
        node = HumidifierNode(actuator_id=actuator_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Humidifier] Stopped by user.")
        node.stop()