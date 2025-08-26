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

class MicrophoneMessage(PubSubMessage):
    pubFreq: float
    type: str
    sensor_id: str
    soundlevelDB: float
    mode: str
    blocked: int

SIMULATED_PROPS = {
    "soundlevelDB",
    "mode",
    "blocked",
}

class MicrophoneNode(Node):
    def __init__(self, sensor_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = None
        self.sensor_id = sensor_id
        self.soundlevelDB = 0.0
        self.mode = ""
        self.blocked = False
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="microphone",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for sensor.microphone
        self.publisher = self.create_publisher(
            topic=f"sensor.microphone.{self.sensor_id}",
            msg_type=MicrophoneMessage,
        )

    def simulate_microphone(self, name: str):
        """
        Simulate dynamic behavior for 'Microphone' actor.
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
            val = self.simulate_microphone(name)
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
            # DEBUG: topic_base = sensor.microphone
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.temperature
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.humidity
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.gas
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.co2
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.ph
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.humiditysensor
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
            msg = MicrophoneMessage(
                pubFreq=self.pub_freq,
                sensor_id=self.sensor_id,
                type="MicrophoneData",
                soundlevelDB=float(self.get_property_value("soundlevelDB")),
                mode=self.get_property_value("mode"),
                blocked=int(self.get_property_value("blocked")),
            )
            print(f"[MicrophoneNode] Publishing to sensor.microphone.{self.sensor_id}: {msg.model_dump()}")
            self.publisher.publish(msg)
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.microphone name
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
        sensor_id = sys.argv[1] if len(sys.argv) > 1 else "microphone_1"
        node = MicrophoneNode(sensor_id=sensor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Microphone] Stopped by user.")
        node.stop()