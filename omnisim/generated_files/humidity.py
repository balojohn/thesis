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

class EnvSensorMessage(PubSubMessage):
    pubFreq: float
    sensor_id: str
    value: float

SIMULATED_PROPS = {
    "value",
}

class HumidityNode(Node):
    def __init__(self, sensor_id: str = "", *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = None
        self.sensor_id = sensor_id
        self.value = 0.0
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="humidity",
            connection_params=conn_params,
            *args, **kwargs
        )

        # Create dedicated publisher for sensor.envsensor.humidity
        self.publisher = self.create_publisher(
            topic=f"sensor.envsensor.humidity.{self.sensor_id}",
            msg_type=EnvSensorMessage,
        )

    def simulate_humidity(self, name: str):
        """
        Simulate dynamic behavior for 'Humidity' actor.
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
            val = self.simulate_humidity(name)
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
            # DEBUG: topic_base = sensor.envsensor.humidity
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.temperature
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.humidity
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.gas
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.co2
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.ph
            # DEBUG: endpoint = Publisher, topic = sensor.envsensor.airquality
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
            msg = EnvSensorMessage(
                pubFreq=self.pub_freq,
                sensor_id=self.sensor_id,
                type="EnvSensorData",
                value=float(self.get_property_value("value")),
            )
            print(f"[HumidityNode] Publishing to sensor.envsensor.humidity.{self.sensor_id}: {msg.model_dump()}")
            self.publisher.publish(msg)
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.humidity name
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
        sensor_id = sys.argv[1] if len(sys.argv) > 1 else "humidity_1"
        node = HumidityNode(sensor_id=sensor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Humidity] Stopped by user.")
        node.stop()