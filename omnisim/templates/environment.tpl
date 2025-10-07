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
{% macro topic_prefix(obj, parent_id=None) %}
    {% set cls = obj.class|lower %}
    {% set typ = obj.type|lower if obj.type else None %}
    {% set name = obj.name|lower %}
    {% if obj.class == "Sensor" %}
        {% if parent_id %}
            composite.{{ parent_id }}.{{ name }}
        {% else %}
            sensor.{{ typ }}.{{ name }}
        {% endif %}
    {% elif obj.class == "Actuator" %}
        {% if parent_id %}
            composite.{{ parent_id }}.{{ name }}
        {% else %}
            actuator.{{ typ }}.{{ name }}
        {% endif %}
    {% elif obj.__class__.__name__ == "CompositeThing" %}
        {% if obj.name == "Robot" %}
            composite.robot
        {% else %}
            composite.{{ name }}
        {% endif %}
    {% else %}
        {{ obj.__class__.__name__|lower }}
    {% endif %}
{% endmacro %}
{# --- recursively register composite children --- #}
{% macro register_composite_children(nodes_path, poses_path, parent_ref, parent_pose, parent_id) %}
    {% set px, py, pth = parent_pose.x, parent_pose.y, parent_pose.theta %}
    {# === Register child composites === #}
    {% for comp in parent_ref.composites %}
        {% set cname = comp.ref.name|lower %}
        {% set cid = parent_id ~ "_" ~ cname %}
        {% set dx = comp.transformation.transformation.dx %}
        {% set dy = comp.transformation.transformation.dy %}
        {% set dth = comp.transformation.transformation.dtheta %}
        {% set cx = px + dx %}
        {% set cy = py + dy %}
        {% set cth = pth + dth -%}
        # Define child of composite {{ cid }}
        {# {{ nodes_path }}["composites"].setdefault("{{ cname }}", {}) #}
        {{ nodes_path }}["composites"].setdefault("{{ cid }}", {
            "sensors": {},
            "actuators": {},
            "composites": {}
        })
        {# {{ poses_path }}["composites"].setdefault("{{ cname }}", {}) #}
        {{ poses_path }}["composites"]["{{ cid }}"] = {
            "x": {{ cx }},
            "y": {{ cy }},
            "theta": {{ cth }},
            "sensors": {},
            "actuators": {},
            "composites": {}
        }
        # Children of composite
        {# Recurse for nested composites -#}
        {{ register_composite_children(
            nodes_path ~ "['composites']['" ~ cid ~ "']",
            poses_path ~ "['composites']['" ~ cid ~ "']",
            comp.ref,
            {'x': cx, 'y': cy, 'theta': cth},
            cid
        ) }}
    {% endfor %}
    {# === Register child sensors === #}
    {% for sen in parent_ref.sensors %}
        {% set sname = sen.ref.name|lower %}
        {% set sid = parent_id ~ "_" ~ sname %}
        {% set dx = sen.transformation.transformation.dx %}
        {% set dy = sen.transformation.transformation.dy %}
        {% set dth = sen.transformation.transformation.dtheta %}
        {% set sx = px + dx %}
        {% set sy = py + dy %}
        {% set sth = pth + dth %}
        {{ nodes_path }}["sensors"].setdefault("{{ sname }}", [])
        {{ poses_path }}["sensors"].setdefault("{{ sname }}", {})
        {{ nodes_path }}["sensors"]["{{ sname }}"].append("{{ sid }}")
        {{ poses_path }}["sensors"]["{{ sname }}"]["{{ sid }}"] = {
            "x": {{ sx }},
            "y": {{ sy }},
            "theta": {{ sth }}
        }
    {% endfor %}
    {# === Register child actuators === #}
    {% for act in parent_ref.actuators %}
        {% set aname = act.ref.name|lower %}
        {% set aid = parent_id ~ "_" ~ aname %}
        {% set dx = act.transformation.transformation.dx %}
        {% set dy = act.transformation.transformation.dy %}
        {% set dth = act.transformation.transformation.dtheta %}
        {% set ax = px + dx %}
        {% set ay = py + dy %}
        {% set ath = pth + dth %}
        {{ nodes_path }}["actuators"].setdefault("{{ aname }}", [])
        {{ poses_path }}["actuators"].setdefault("{{ aname }}", {})
        {{ nodes_path }}["actuators"]["{{ aname }}"].append("{{ aid }}")
        {{ poses_path }}["actuators"]["{{ aname }}"]["{{ aid }}"] = {
            "x": {{ ax }},
            "y": {{ ay }},
            "theta": {{ ath }}
        }
    {% endfor %}
{% endmacro %}
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
        self.pantilts = {}
        self.handle_offsets = {}
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
            {# Initialization of composites #}
            {% if category == "composites" %}
        if "{{ node_name }}" not in self.nodes["composites"]:
            self.nodes["composites"]["{{ node_name }}"] = {}
            self.poses["composites"]["{{ node_name }}"] = {}
        
        if "{{ inst }}" not in self.nodes["composites"]["{{ node_name }}"]:
            # Initialize node + pose dicts if not existing
            self.nodes["composites"]["{{ node_name }}"]["{{ inst }}"] = {
                "sensors": {},
                "actuators": {},
                "composites": {}
            }
            self.poses["composites"]["{{ node_name }}"]["{{ inst }}"] = {
                "sensors": {},
                "actuators": {},
                "composites": {}
            }
            {% else %}
                {# Initialization of things with or without type #}
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
            {% endif %}
        
        # Define {{ inst }} node
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
            },
            {% if category == "composites" %}
            "initial_pose": {
                "x": {{ p.pose.x }},
                "y": {{ p.pose.y }},
                "theta": {{ p.pose.theta }}
            }
            {% endif %}
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
            {% if category == "composites" %}
        self.poses["{{ category }}"]["{{ node_name }}"]["{{ inst }}"].update({
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        })
            {% else %}
        self.poses["{{ category }}"]["{{ node_name }}"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        {% endif %}
        {% endif %}
        self.tree[self.env_name.lower()].append("{{ inst }}")
        
        {% if p.nodeclass == "CompositePlacement" %}
        {{ register_composite_children(
            "self.nodes['composites']['" ~ node_name ~ "']['" ~ inst ~ "']",
            "self.poses['composites']['" ~ node_name ~ "']['" ~ inst ~ "']",
            p.ref,
            {'x': p.pose.x, 'y': p.pose.y, 'theta': p.pose.theta},
            inst
        ) }}
        {% endif %}
        # Define {{ inst }} subscriber
        {% set topic_base = topic_prefix(p.ref, parent_id=inst if p.nodeclass == "CompositePlacement" else None) | trim %}
        self.{{ inst }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_base }}.{{ inst }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, id="{{ inst }}": \
                self.node_pose_callback({
                    "class": "{{ class }}",
                    "type": "{{ node_type if node_type else '' }}",
                    "name": "{{ node_name }}",
                    "id": id,
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
        return node_pose_callback(self.tree, self.poses, self.pantilts, self.handle_offsets, self.log, node)

    def print_tf_tree(self):
        """Print a hierarchical TF tree of all nodes with poses."""
        def format_pose(p):
            """Format pose or linear segment as readable text."""
            if "start" in p and "end" in p:
                s, e = p["start"], p["end"]
                return f"(start=({s['x']:.3f},{s['y']:.3f}) -> end=({e['x']:.3f},{e['y']:.3f}))"
            return f"(x={p['x']:.3f}, y={p['y']:.3f}, theta={p['theta']:.3f} deg)"

        def is_pose_dict(d):
            """Return True if dict represents a pose (has x/y/theta or start/end)."""
            return (
                isinstance(d, dict)
                and (
                    all(k in d for k in ["x", "y", "theta"])
                    or ("start" in d and "end" in d)
                )
            )

        def print_composite_children(comp_data, indent):
            """Print children of a composite (sensors, actuators, nested composites)."""
            if not isinstance(comp_data, dict):
                return
            
            # Print sensors
            if "sensors" in comp_data and comp_data["sensors"]:
                for sensor_name, sensor_instances in comp_data["sensors"].items():
                    if isinstance(sensor_instances, dict):
                        for sensor_id, sensor_pose in sensor_instances.items():
                            if is_pose_dict(sensor_pose):
                                self.log.info(f"{'    ' * indent}- {sensor_id} @ {format_pose(sensor_pose)}")
            
            # Print actuators
            if "actuators" in comp_data and comp_data["actuators"]:
                for actuator_name, actuator_instances in comp_data["actuators"].items():
                    if isinstance(actuator_instances, dict):
                        for actuator_id, actuator_pose in actuator_instances.items():
                            if is_pose_dict(actuator_pose):
                                self.log.info(f"{'    ' * indent}- {actuator_id} @ {format_pose(actuator_pose)}")
            
            # Print nested composites recursively
            if "composites" in comp_data and comp_data["composites"]:
                for comp_name, comp_instances in comp_data["composites"].items():
                    if isinstance(comp_instances, dict):
                        for comp_id, nested_comp_data in comp_instances.items():
                            if is_pose_dict(nested_comp_data):
                                self.log.info(f"{'    ' * indent}- {comp_id} @ {format_pose(nested_comp_data)}")
                                # Recursively print children of nested composite
                                print_composite_children(nested_comp_data, indent + 1)

        def print_recursive(name, data, indent=0):
            """Recursively print node hierarchy."""
            prefix = "    " * indent + "- "

            # Pose node
            if is_pose_dict(data):
                self.log.info(f"{prefix}{name} @ {format_pose(data)}")
                
                # If this is a composite instance, print its children
                print_composite_children(data, indent + 1)
                return

            # Non-pose node: may contain dicts or lists
            if isinstance(data, dict):
                self.log.info(f"{prefix}{name}")
                for key, val in data.items():
                    print_recursive(key, val, indent + 1)
            elif isinstance(data, list):
                for elem in data:
                    self.log.info(f"{prefix}{elem}")

        # Print environment header
        self.log.info(f"- {self.env_name}")

        # Recursively print each category
        for category, content in self.poses.items():
            if not content:
                continue
            self.log.info("    - %s", category.capitalize())
            for key, val in content.items():
                print_recursive(key, val, indent=2)

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
