import random
import math
import sys
import threading
import subprocess
import time
import redis
from commlib.msg import PubSubMessage
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

class PoseMessage(PubSubMessage):
    # Matches your geometry.dtype Pose { position{ x,y,z }, orientation{ roll,pitch,yaw } }
    position: dict   # {'x': float, 'y': float, 'z': float}
    orientation: dict  # {'roll': float, 'pitch': float, 'yaw': float}

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
    "distance",
    "hfov",
    "vfov",
    "minRange",
    "maxRange",
}

class SonarNode(Node):
    def __init__(self, sensor_id: str = "", initial_pose: dict | None = None, *args, **kwargs):
        self.pub_freq = 1.0
        self.dispersion = None
        self.sensor_id = sensor_id
        self.distance = 0.0
        self.hfov = 60.0
        self.vfov = 37.9
        self.minRange = 10.0
        self.maxRange = 250.0
        
        # runtime pose (2D convenience); z/roll/pitch kept 0 for now
        self.x = (initial_pose or {}).get('x', 0.0)
        self.y = (initial_pose or {}).get('y', 0.0)
        self.theta = (initial_pose or {}).get('theta', 0.0)  # degrees
        
        # --- simple motion (so pose changes) ---
        self._last_t = time.monotonic()
        self.vx = 0.10    # m/s along +x (adjust or set to 0.0 if you want static)
        self.vy = 0.10    # m/s along +y
        self.omega = 10.0 # deg/s yaw
        
        super().__init__(
            node_name="sonar",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )

        self.pose_publisher = self.create_publisher(
            topic=f"sensor.rangefinder.sonar.{self.sensor_id}.pose",
            msg_type=PoseMessage
        )
            
        # Create dedicated publisher for sensor.rangefinder.sonar
        self.data_publisher = self.create_publisher(
            topic=f"sensor.rangefinder.sonar.{self.sensor_id}",
            msg_type=RangeMessage,
        )
    
    def _integrate_motion(self):
        """Very small kinematic integrator so pose updates each tick."""
        now = time.monotonic()
        dt = now - self._last_t
        self._last_t = now

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.theta += self.omega * dt
        # keep theta in [0, 360)
        if self.theta >= 360.0 or self.theta <= -360.0:
            self.theta = self.theta % 360.0

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
            # --- update pose then publish pose ---
            self._integrate_motion()
            msg_pose = PoseMessage(
                position={'x': self.x, 'y': self.y, 'z': 0.0},
                orientation={'roll': 0.0, 'pitch': 0.0, 'yaw': self.theta}
            )
            print(f"[SonarNode] Publishing to sensor.rangefinder.sonar.{self.sensor_id}.pose: {msg_pose.model_dump()}")
            self.pose_publisher.publish(msg_pose)
            msg_data = RangeMessage(
                pubFreq=self.pub_freq,
                sensor_id=self.sensor_id,
                type="RangeData",
                distance=float(self.get_property_value("distance")),
                hfov=int(self.get_property_value("hfov")),
                vfov=int(self.get_property_value("vfov")),
                minRange=float(self.get_property_value("minRange")),
                maxRange=float(self.get_property_value("maxRange")),
            )
            print(f"[SonarNode] Publishing to sensor.rangefinder.sonar.{self.sensor_id}: {msg_data.model_dump()}")
            self.data_publisher.publish(msg_data)
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