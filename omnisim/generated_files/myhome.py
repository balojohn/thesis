import sys, time, threading, subprocess, redis
from typing import Dict, Tuple, Any
from commlib.msg import PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from .temperature import EnvSensorMessage, PoseMessage
from .fire import FireMessage, PoseMessage

class EnvironmentNode(Node):
    def __init__(self, env_name: str = "environment", *args, **kwargs):
        super().__init__(
            node_name=f"{env_name.lower()}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        self.poses: Dict[Tuple[str,str], dict] = {}
        self.data: Dict[Tuple[str,str], Any] = {}
        self._subs = []

        # ---- Temperature subscriber ----
        self._subs.append(self.create_subscriber(
            topic=f"sensor.envsensor.temperature.temperature_1.pose",
            msg_type=PoseMessage,
            on_message=self._temperature_1_pose
        ))

        self._subs.append(self.create_subscriber(
            topic=f"sensor.envsensor.temperature.temperature_1",
            msg_type=EnvSensorMessage,
            on_message=self._temperature_1_data
        ))

        # ---- Fire subscriber ----
        self._subs.append(self.create_subscriber(
            topic=f"actor.envactor.fire.fire_1.pose",
            msg_type=PoseMessage,
            on_message=self._fire_1_pose
        ))

        self._subs.append(self.create_subscriber(
            topic=f"actor.envactor.fire.fire_1",
            msg_type=FireMessage,
            on_message=self._fire_1_data
        ))

    # ---- Callbacks ----
    def _temperature_1_pose(self, msg: PoseMessage):
        x = float(msg.position.get('x', 0.0))
        y = float(msg.position.get('y', 0.0))
        yaw = float(msg.orientation.get('yaw', 0.0))
        self.poses[("envsensor", "temperature_1")] = {'x': x, 'y': y, 'theta': yaw}
        print(f"[Environment] Pose [envsensor/temperature_1] -> x={x:.2f}, y={y:.2f}, theta={yaw:.1f}")

    def _temperature_1_data(self, msg: PubSubMessage):
        payload = msg.model_dump() if hasattr(msg, "model_dump") else dict(getattr(msg, "__dict__", {}))
        self.data[("envsensor", "temperature_1")] = payload
        print(f"[Environment] Data [envsensor/temperature_1]  payload={payload}")

    def _fire_1_pose(self, msg: PoseMessage):
        x = float(msg.position.get('x', 0.0))
        y = float(msg.position.get('y', 0.0))
        yaw = float(msg.orientation.get('yaw', 0.0))
        self.poses[("envactor", "fire_1")] = {'x': x, 'y': y, 'theta': yaw}
        print(f"[Environment] Pose [envactor/fire_1] -> x={x:.2f}, y={y:.2f}, theta={yaw:.1f}")

    def _fire_1_data(self, msg: PubSubMessage):
        payload = msg.model_dump() if hasattr(msg, "model_dump") else dict(getattr(msg, "__dict__", {}))
        self.data[("envactor", "fire_1")] = payload
        print(f"[Environment] Data [envactor/fire_1]  payload={payload}")

    def start(self):
        # Launch commlib internal loop in a background thread
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print("[Environment] Running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)  # keep main thread alive
        except KeyboardInterrupt:
            print("[Environment] Interrupted by user.")
            self.stop()

if __name__ == '__main__':
    try:
        redis.Redis(host='localhost', port=6379).ping()
        print("[Redis] Connected successfully.")
    except redis.exceptions.ConnectionError:
        print("[Redis] Not running. Start Redis server first.")
        sys.exit(1)

    node = EnvironmentNode(env_name="MyHome")
    try:
        node.start()
    except KeyboardInterrupt:
        print(f"\n[MyHome] Stopped by user.")
        node.stop()