import sys
import threading
import time
import math
import redis
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from ...utils.geometry import PoseMessage
{% macro topic_prefix(obj) -%}
    {%- if obj.class is defined and obj.class == "Sensor" -%}
        sensor.{{ obj.type|lower }}
    {%- elif obj.class is defined and obj.class == "Actuator" -%}
        actuator.{{ obj.type|lower }}
    {%- elif obj.__class__.__name__ == "CompositeThing" -%}
        composite.{{ obj.name|lower }}
    {%- elif obj.__class__.__name__ == "CompositeThing" and obj.name == "Robot" -%}
        composite.robot
    {%- elif obj.__class__.__name__ == "EnvActor" -%}
        actor.{{ obj.name|lower }}
    {%- else -%}
        {{ obj.__class__.__name__|lower }}
    {%- endif -%}
{%- endmacro %}
# Import generated child nodes
{% for posed_sensor in composite.sensors %}
from .{{ posed_sensor.ref.name.lower() }} import {{ posed_sensor.ref.name }}Node
{% endfor %}
{% for posed_actuator in composite.actuators %}
from .{{ posed_actuator.ref.name.lower() }} import {{ posed_actuator.ref.name }}Node
{% endfor %}
{% for posed_cthing in composite.composites %}
from .{{ posed_cthing.ref.name.lower() }} import {{ posed_cthing.ref.name }}Node
{% endfor %}

class {{ composite.name }}Node(Node):
    def __init__(self, instance_id: str = None, *args, **kwargs):
        super().__init__(
            node_name="{{ composite.name.lower() }}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        self.instance_id = instance_id or "{{ composite.instance_id if composite.instance_id else composite.name|lower ~ '_1' }}"
        self.running = True

        # --- composite pose (global) ---
        self.x = kwargs.get("initial_pose", {}).get("x", 0.0)
        self.y = kwargs.get("initial_pose", {}).get("y", 0.0)
        self.theta = kwargs.get("initial_pose", {}).get("theta", 0.0)
        self._last_t = time.monotonic()
        self.vx, self.vy, self.omega = 0.1, 0.0, 10.0  # simple motion model

        # --- Pose publisher for composite itself ---
        self.pose_publisher = self.create_publisher(
            topic=f"{{ topic_prefix(composite) }}.{self.instance_id}.pose",
            msg_type=PoseMessage
        )

        # --- Children ---
        self.children = {}

        {% for posed_sensor in composite.sensors %}
        {% set tf = posed_sensor.transformation.transformation if posed_sensor.transformation else None %}
        self.children["{{ posed_sensor.ref.name.lower() }}"] = {{ posed_sensor.ref.name }}Node(
            sensor_id=f"{instance_id}_{{ posed_sensor.ref.name.lower() }}",
            initial_pose={
                'x': {{ tf.translation.x if tf and tf.translation else 0.0 }},
                'y': {{ tf.translation.y if tf and tf.translation else 0.0 }},
                'theta': {{ tf.rotation.yaw if tf and tf.rotation else 0.0 }}
            }
        )
        {% endfor %}

        {% for posed_actuator in composite.actuators %}
        {% set tf = posed_actuator.transformation.transformation if posed_actuator.transformation else None %}
        self.children["{{ posed_actuator.ref.name.lower() }}"] = {{ posed_actuator.ref.name }}Node(
            actuator_id=f"{instance_id}_{{ posed_actuator.ref.name.lower() }}",
            initial_pose={
                'x': {{ tf.translation.x if tf and tf.translation else 0.0 }},
                'y': {{ tf.translation.y if tf and tf.translation else 0.0 }},
                'theta': {{ tf.rotation.yaw if tf and tf.rotation else 0.0 }}
            }
        )
        {% endfor %}

        {% for posed_cthing in composite.composites %}
        self.children["{{ posed_cthing.ref.name.lower() }}"] = {{ posed_cthing.ref.name }}Node(
            instance_id=f"{self.instance_id}_{{ posed_cthing.ref.name.lower() }}"
        )
        {% endfor %}

    def _integrate_motion(self):
        """Simple kinematics for composite pose"""
        now = time.monotonic()
        dt = now - self._last_t
        self._last_t = now

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.theta = (self.theta + self.omega * dt) % 360.0

    def start(self):
        # Launch commlib's loop in the background
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)

        print(f"[Composite] Running {{ composite.name }} with id={self.instance_id}")
        # Start child nodes
        for name, node in self.children.items():
            print(f"  -> starting child {name}")
            node.running = True
            threading.Thread(target=node.start, daemon=True).start()

        # Main loop: update composite pose
        while self.running:
            self._integrate_motion()
            msg_pose = PoseMessage(
                x=self.x,
                y=self.y,
                theta=self.theta
            )
            self.pose_publisher.publish(msg_pose)
            print(f"[{{ composite.name }}Node] Publishing pose to {self.pose_publisher.topic}: {msg_pose.model_dump()}")
            time.sleep(1.0)
    
    def stop(self):
        print(f"[Composite] Stopping MyRobot and children...")
        self.running = False
        for node in self.children.values():
            try:
                node.stop()
                if hasattr(node, "thread") and node.thread:
                    node.thread.join(timeout=1.0)
            except Exception:
                pass
        super().stop()
        print(f"[Composite] Stopped.")

if __name__ == "__main__":
    try:
        redis.Redis(host='localhost', port=6379).ping()
        print("[Redis] Connected successfully.")
    except redis.exceptions.ConnectionError:
        print("[Redis] Not running. Start Redis server first.")
        sys.exit(1)

    rid = sys.argv[1] if len(sys.argv) > 1 else "{{ composite.name.lower() }}_1"
    node = {{ composite.name }}Node(instance_id=rid)
    try:
        node.start()
    except KeyboardInterrupt:
        print(f"\n[Main] {{ composite.name }} shutdown.")
        node.stop()
        sys.exit(0)
