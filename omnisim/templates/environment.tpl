import sys, time, threading, logging, redis
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import math
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
# from ...utils.utils import *
# from ...utils.geometry import PoseMessage
from omnisim.utils.utils import *
from omnisim.utils.geometry import PoseMessage
from omnisim.utils.utils import (
    node_pose_callback,
)
# --- import affection handlers ---
from omnisim.utils.affections import (
    handle_temperature_sensor,
    handle_humidity_sensor,
    handle_gas_sensor,
    handle_microphone_sensor,
    handle_light_sensor,
    handle_camera_sensor,
    handle_rfid_sensor,
    handle_area_alarm,
    handle_linear_alarm,
    handle_distance_sensor,
    check_affectability,
)
{% macro topic_prefix(obj) -%}
    {%- set cls = obj.class|lower -%}
    {%- set typ = obj.type|lower if obj.type else None -%}
    {%- set name = obj.name|lower -%}
    {%- if obj.class is defined and obj.class == "Sensor" -%}
        {{ cls }}.{{ typ }}.{{ name }}
    {%- elif obj.class is defined and obj.class == "Actuator" -%}
        {{ cls }}.{{ typ }}.{{ name }}
    {%- elif obj.__class__.__name__ == "CompositeThing" and obj.name == "Robot" -%}
        composite.robot
    {%- elif obj.__class__.__name__ == "CompositeThing" -%}
        composite.{{ name }}
    {%- else -%}
        {{ obj.__class__.__name__|lower }}
    {%- endif -%}
{%- endmacro %}
{# --- imports for messages actually used in this env --- #}
{% set placements = (environment.things or []) + (environment.actors or []) + (environment.composites or []) %}
{% for p in placements %}
  {% set ref = p.ref %}
  {% set base = p.poseTopic if p.poseTopic else topic_prefix(ref) %}
  {# now match comms publishers #}
  {% for comm in comms.communications %}
    {% for e in comm.endpoints %}
      {% if e.__class__.__name__ == "Publisher" and e.topic.startswith(base) and e.msg is not none %}
        {% if e.msg.name not in ns.imported %}
from .{{ ref.name|lower }} import {{ e.msg.name }}, PoseMessage
          {% set ns.imported = ns.imported + [e.msg.name] %}
        {% endif %}
      {% endif %}
    {% endfor %}
  {% endfor %}
{% endfor %}

class {{ environment.name }}Node(Node):
    def __init__(self, env_name: str, *args, **kwargs):
        super().__init__(
            node_name=f"{env_name.lower()}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        self.env_name = env_name
        self.poses = {
            "sensors": {},
            "actuators": {},
            "actors": {},
            "composites": {},
            "obstacles": {}
        }

        self.nodes = {
            "sensors": {},
            "actuators": {},
            "actors": {},
            "composites": {},
            "obstacles": {}
        }

        # Tree structure (who hosts what)
        self.tree = {}
        self.tree[self.env_name.lower()] = []

        {# Collect all placements into one list with a category tag #}
        {% set placements = [] %}
        {% for t in environment.things or [] %}
            {% set _ = placements.append({
                "ref": t.ref,
                "inst": t.instance_id if t.instance_id else t.ref.name|lower,
                "pose": t.pose,
                "class": t.ref.class,
                "nodeclass": t.__class__.__name__,
                "category": "thing"
            }) %}
        {% endfor %}
        {% for a in environment.actors or [] %}
            {% set _ = placements.append({
                "ref": a.ref,
                "inst": a.instance_id if a.instance_id else a.ref.name|lower,
                "pose": a.pose,
                "class": a.ref.class,
                "nodeclass": a.__class__.__name__,
                "category": "actor"
            }) %}
        {% endfor %}
        {% for o in environment.obstacles or [] %}
            {% set _ = placements.append({
                "ref": o.ref,
                "inst": o.instance_id if o.instance_id else o.ref.name|lower,
                "pose": o.pose,
                "class": o.ref.class,
                "nodeclass": o.__class__.__name__,
                "category": "obstacle"
            }) %}
        {% endfor %}

        {% for p in placements if p.category != "obstacle" %}
        {% set inst = p.inst %}
        {% if p.category == "thing" and p.class == "Sensor" %}
            {% set category = "sensors" %}
            {% set class = "sensor" %}
            {% set node_type = p.ref.type|lower if p.ref.type else None %}
            {% set node_name = p.ref.name|lower %}
        {% elif p.category == "thing" and p.class == "Actuator" %}
            {% set category = "actuators" %}
            {% set class = "actuator" %}
            {% set node_type = p.ref.type|lower if p.ref.type else None %}
            {% set node_name = p.ref.name|lower %}
        {% elif p.category == "thing" and p.nodeclass == "CompositePlacement" %}
            {% set category = "composites" %}
            {% set class = "composite" %}
            {% set node_type = p.ref.type|lower if p.ref.type else None %}
            {% set node_name = p.ref.name|lower %}
        {% elif p.category == "actor" %}
            {% set category = "actors" %}
            {% set class = "actor" %}
            {% set node_type = p.ref.type|lower if p.ref.type else None %}
            {% set node_name = p.ref.name|lower %}
        {% elif p.category == "obstacle" %}
            {% set category = "obstacles" %}
            {% set class = "obstacle" %}
            {% set node_type = p.ref.type|lower if p.ref.type else None %}
            {% set node_name = p.ref.name|lower %}
        {% endif %}
        # Define {{ inst }} node
        {% if node_type %}
        if "{{ node_type }}" not in self.nodes["{{ category }}"]:
            self.nodes["{{ category }}"]["{{ node_type }}"] = {}
            self.poses["{{ category }}"]["{{ node_type }}"] = {}
        if "{{ node_name }}" not in self.nodes["{{ category }}"]["{{ node_type }}"]:
            self.nodes["{{ category }}"]["{{ node_type }}"]["{{ node_name }}"] = []
            self.poses["{{ category }}"]["{{ node_type }}"]["{{ node_name }}"] = {}
        if "{{ inst }}" not in self.nodes["{{ category }}"]["{{ node_type }}"]["{{ node_name }}"]:
            self.nodes["{{ category }}"]["{{ node_type }}"]["{{ node_name }}"].append("{{ inst }}")
        {% else %}
        if "{{ node_name }}" not in self.nodes["{{ category }}"]:
            self.nodes["{{ category }}"]["{{ node_name }}"] = []
            self.poses["{{ category }}"]["{{ node_name }}"] = {}
        if "{{ inst }}" not in self.nodes["{{ category }}"]["{{ node_name }}"]:
            self.nodes["{{ category }}"]["{{ node_name }}"].append("{{ inst }}")
        {% endif %}

        self.nodes["{{ inst }}"] = {
            "class": "{{ class }}",
            {% if node_type %}
            "type": "{{ node_type }}",
            {% endif %}
            "name": "{{ node_name }}",
            "id": "{{ inst }}",
            "properties": {
                {% set excluded = [
                    "class","type","shape","pubFreq","name","dataModel",
                    "_tx_position","_tx_model","_tx_position_end","parent",
                    "actuators","sensors","composites"
                ] %}
                {% for attr, val in p.ref.__dict__.items() 
                if attr not in excluded and val is not none %}
                "{{ attr }}":
                    {%- if val is number -%} {{ val }}
                    {%- elif val is string -%} "{{ val }}"
                    {%- elif val.__class__.__name__ in ["Gaussian","Uniform","Quadratic"] -%}
                        {
                        {%- for k,v in val.__dict__.items()
                        if k not in ["_tx_model","_tx_position","_tx_position_end","parent","ref"] and v is not none -%}
                            "{{ k }}": {{ v|tojson }},
                        {%- endfor -%}
                        }
                    {%- else -%} {{ val|tojson }}
                    {%- endif -%},
                {% endfor %}
            }
        }
        
        # Define {{ inst }} pose
        {% if node_name == "linearalarm" %}
        self.poses["{{ category }}"]["{{ node_type }}"]["{{ node_name }}"]["{{ inst }}"] = {
            "start": {
                "x": {{ p.ref.shape.points[0].x }},
                "y": {{ p.ref.shape.points[0].y }}
            },
            "end": {
                "x": {{ p.ref.shape.points[1].x }},
                "y": {{ p.ref.shape.points[1].y }}
            }
        }
        {% elif node_type %}
        self.poses["{{ category }}"]["{{ node_type }}"]["{{ node_name }}"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        {% else %}
        self.poses["{{ category }}"]["{{ node_name }}"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        {% endif %}
        self.tree[self.env_name.lower()].append("{{ inst }}")
        
        # Define {{ inst }} subscriber
        self.{{ inst }}_pose_sub = self.create_subscriber(
            topic=f"{{ class }}{% if node_type %}.{{ node_type }}{% endif %}.{{ node_name }}.{{ inst }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ inst }}": \
                self.node_pose_callback({
                    "class": "{{ class }}",
                    "type": "{{ node_type if node_type else '' }}",
                    "name": "{{ node_name }}",
                    "id": name,
                    "x": msg.x,
                    "y": msg.y,
                    "theta": msg.theta
                })
        )

        {% endfor %}
    {#
        # ---- live plotting setup ----
        plt.ion()
        self._fig, self._ax = plt.subplots()
        self._fig.show()
        self._fig.canvas.draw()

    def plot_poses(self):
        self._ax.clear()
        for category, nodes in self.poses.items():
            for name, p in nodes.items():
                x, y, theta = p["x"], p["y"], math.radians(p["theta"])
                self._ax.arrow(
                    x, y,
                    0.5 * math.cos(theta), 0.5 * math.sin(theta),
                    head_width=0.1, length_includes_head=True
                )
                self._ax.text(x, y, name, fontsize=8)
        self._ax.set_aspect("equal")
        self._ax.grid(True)
    
        # Draw updates on the existing window
        self._fig.canvas.draw()
        self._fig.canvas.flush_events()
    #}
    # Wrappers for affection and pose utils
    def handle_temperature_sensor(self, sensor_id: str):
        return handle_temperature_sensor(self.nodes, self.poses, self.log, sensor_id)

    def handle_humidity_sensor(self, sensor_id: str):
        return handle_humidity_sensor(self.nodes, self.poses, self.log, sensor_id)

    def handle_gas_sensor(self, sensor_id: str):
        return handle_gas_sensor(self.nodes, self.poses, self.log, sensor_id)
    
    def handle_microphone_sensor(self, sensor_id: str):
        return handle_microphone_sensor(self.nodes, self.poses, self.log, sensor_id)

    def handle_light_sensor(self, sensor_id: str):
        return handle_light_sensor(self.nodes, self.poses, self.log, sensor_id)
    
    def handle_camera_sensor(self, sensor_id: str, with_robots):
        return handle_camera_sensor(self.nodes, self.poses, self.log, sensor_id, with_robots)
    
    def handle_rfid_sensor(self, sensor_id: str):
        return handle_rfid_sensor(self.nodes, self.poses, self.log, sensor_id)
    
    def handle_area_alarm(self, sensor_id: str):
        return handle_area_alarm(self.nodes, self.poses, self.log, sensor_id)

    def handle_linear_alarm(self, sensor_id: str, lin_alarms_robots=None):
        return handle_linear_alarm(self.nodes, self.poses, self.log, sensor_id, lin_alarms_robots)
    
    def handle_distance_sensor(self, sensor_id: str):
        return handle_distance_sensor(self.nodes, self.poses, self.log, sensor_id)
    
    def check_affectability(self, sensor_id: str, env_properties, lin_alarms_robots=None):
        return check_affectability(self.nodes, self.poses, self.log, sensor_id, env_properties, lin_alarms_robots)

    def node_pose_callback(self, node: dict):
        return node_pose_callback(self.poses, self.log, node)

    def print_tf_tree(self):
        self.log.info(f"\n- {self.env_name}")

        def format_pose(p):
            return f"@ (x={p['x']:.2f}, y={p['y']:.2f}, theta={p['theta']:.1f} deg)"

        def search_tree_recursive(d, indent=0):
            for name, sub in d.items():
                if isinstance(sub, dict) and all(k in sub for k in ["x", "y", "theta"]):
                    # It's a pose dict
                    self.log.info("%s- %s %s", "    " * indent, name, format_pose(sub))
                elif isinstance(sub, dict):
                    # Go deeper
                    self.log.info("%s- %s", "    " * indent, name)
                    search_tree_recursive(sub, indent + 1)

        # Sensors
        if self.poses["sensors"]:
            self.log.info("    - Sensors")
            search_tree_recursive(self.poses["sensors"], 2)

        # Actuators
        if self.poses["actuators"]:
            self.log.info("    - Actuators")
            search_tree_recursive(self.poses["actuators"], 2)

        # Obstacles
        if self.poses["obstacles"]:
            self.log.info("    - Obstacles")
            search_tree_recursive(self.poses["obstacles"], 2)

        # Actors
        if self.poses["actors"]:
            self.log.info("    - Actors")
            search_tree_recursive(self.poses["actors"], 2)

        # Composites
        if self.poses["composites"]:
            self.log.info("    - Composites")
            search_tree_recursive(self.poses["composites"], 2)

    def start(self):
        # Launch commlib internal loop in a background thread
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        self.log.info("Running. Press Ctrl+C to stop.")
        try:
            while True:
                self.print_tf_tree()
                time.sleep(1.0)  # keep main thread alive
        except KeyboardInterrupt:
            self.log.warning("Interrupted by user.")
            self.stop()

if __name__ == '__main__':
    try:
        redis.Redis(host='localhost', port=6379).ping()
        print("[Redis] Connected successfully.")
    except redis.exceptions.ConnectionError:
        print("[Redis] Not running. Start Redis server first.")
        sys.exit(1)

    node = {{ environment.name }}Node(env_name="{{ environment.name }}")
    try:
        node.start()
    except KeyboardInterrupt:
        node.log.info("Stopped by user.")
        node.stop()
