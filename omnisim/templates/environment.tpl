import sys, time, threading, logging, redis, math
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from omnisim.utils.geometry import PoseMessage
from omnisim.utils.utils import (
    node_pose_callback,
)
# --- import affection handlers ---
from omnisim.utils.affections import (
    handle_temperature_sensor, handle_humidity_sensor, handle_gas_sensor,
    handle_microphone_sensor, handle_light_sensor, handle_camera_sensor,
    handle_rfid_sensor, handle_area_alarm, handle_linear_alarm,
    handle_distance_sensor, check_affectability,
)
{% macro topic_prefix(obj, parent=None) -%}
    {# parent is a tuple like ("pantilt", "pt_1") #}
    {% set cls = obj.class|lower %}
    {% set type_part = obj.type|lower if obj.type is defined else obj.__class__.__name__|lower %}
    {% set subtype = obj.subtype|lower if obj.subtype is defined else None %}
    {% set ptype = parent[0] if parent and parent|length > 0 else None %}
    {% set pid = parent[1] if parent and parent|length > 1 else None %}

    {% if cls == "sensor" %}
        {% if ptype and pid %}
            composite.{{ ptype }}.{{ pid }}.sensor.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% else %}
            sensor.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% endif %}
    {% elif cls == "actuator" %}
        {% if ptype and pid %}
            composite.{{ ptype }}.{{ pid }}.actuator.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% else %}
            actuator.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% endif %}
    {% elif obj.__class__.__name__ == "CompositeThing" %}
        {% if ptype and pid %}
            composite.{{ ptype }}.{{ pid }}.composite.{{ type_part }}
        {% else %}
            composite.{{ type_part }}
        {% endif %}
    {% else %}
        composite.{{ type_part }}
    {% endif %}
{%- endmacro %}
{# --- recursively register composite children --- #}
{% macro register_composite_children(nodes_path, poses_path, parent_ref, parent_pose, parent_id) %}
    {% set px, py, pth = parent_pose.x, parent_pose.y, parent_pose.theta %}
    {# === Register child composites === #}
    {% for comp in parent_ref.composites %}
        {% set cname = comp.ref.name|lower %}
        {% set cid = cname %}
        {% set dx = comp.transformation.transformation.dx %}
        {% set dy = comp.transformation.transformation.dy %}
        {% set dth = comp.transformation.transformation.dtheta %}
        {# Use apply_transformation to compose absolute pose #}
        {% set abs_pose = apply_transformation({'x': px, 'y': py, 'theta': pth},
                                            {'x': dx, 'y': dy, 'theta': dth}) %}
        {% set cx = abs_pose.x %}
        {% set cy = abs_pose.y %}
        {% set cth = abs_pose.theta %}
        {# --- determine safe composite key --- #}
        {% if comp.ref.type %}
            {% set ctype = comp.ref.type|lower %}
        {% elif comp.ref.subtype is defined and comp.ref.subtype %}
            {% set ctype = comp.ref.subtype|lower %}
        {% else %}
            {% set ctype = comp.ref.__class__.__name__|lower %}
        {% endif -%}
        # Define child of composite {{ cid }}
        {{ nodes_path }}["composites"].setdefault("{{ ctype }}", {})
        {{ poses_path }}["composites"].setdefault("{{ ctype }}", {})
        {{ nodes_path }}["composites"]["{{ ctype }}"].setdefault("{{ cid }}", {
            "sensors": {},
            "actuators": {},
            "composites": {}
        })
        {{ poses_path }}["composites"]["{{ ctype }}"]["{{ cid }}"] = {
            "x": {{ cx }},
            "y": {{ cy }},
            "theta": {{ cth }},
            "sensors": {},
            "actuators": {},
            "composites": {}
        }
        # Recurse for deeper composites
        {{ register_composite_children(
            nodes_path ~ "['composites']['" ~ ctype ~ "']['" ~ cid ~ "']",
            poses_path ~ "['composites']['" ~ ctype ~ "']['" ~ cid ~ "']",
            comp.ref,
            {'x': cx, 'y': cy, 'theta': cth},
            cid
        ) }}
    {% endfor %}

    {# === Register child sensors === #}
    {% for sen in parent_ref.sensors %}
        {% set sname = sen.ref.name|lower %}
        {% set sid = sname %}
        {% set dx = sen.transformation.transformation.dx %}
        {% set dy = sen.transformation.transformation.dy %}
        {% set dth = sen.transformation.transformation.dtheta %}
        {% set s_pose = apply_transformation({'x': px, 'y': py, 'theta': pth},
                                     {'x': dx, 'y': dy, 'theta': dth}) %}
        {% set sx = s_pose.x %}
        {% set sy = s_pose.y %}
        {% set sth = s_pose.theta %}
        {% set stype = sen.ref.type|lower if sen.ref.type else sen.ref.__class__.__name__|lower %}
        {% set ssub = sen.ref.subtype|lower if sen.ref.subtype is defined and sen.ref.subtype and sen.ref.subtype|lower != stype else None %}
        {% if ssub %}
        {{ nodes_path }}["sensors"].setdefault("{{ stype }}", {}).setdefault("{{ ssub }}", {})
        {{ poses_path }}["sensors"].setdefault("{{ stype }}", {}).setdefault("{{ ssub }}", {})
        {{ nodes_path }}["sensors"]["{{ stype }}"]["{{ ssub }}"].setdefault("{{ sid }}", {})
        {{ poses_path }}["sensors"]["{{ stype }}"]["{{ ssub }}"]["{{ sid }}"] = {
        {% else %}
        {{ nodes_path }}["sensors"].setdefault("{{ stype }}", {})
        {{ poses_path }}["sensors"].setdefault("{{ stype }}", {})
        {{ nodes_path }}["sensors"]["{{ stype }}"].setdefault("{{ sid }}", {})
        {{ poses_path }}["sensors"]["{{ stype }}"]["{{ sid }}"] = {
        {% endif %}
            "x": {{ sx }},
            "y": {{ sy }},
            "theta": {{ sth }}
        }
    {% endfor %}

    {# === Register child actuators === #}
    {% for act in parent_ref.actuators %}
        {% set aname = act.ref.name|lower %}
        {% set aid = aname %}
        {% set dx = act.transformation.transformation.dx %}
        {% set dy = act.transformation.transformation.dy %}
        {% set dth = act.transformation.transformation.dtheta %}
        {% set a_pose = apply_transformation({'x': px, 'y': py, 'theta': pth},
                                     {'x': dx, 'y': dy, 'theta': dth}) %}
        {% set ax = a_pose.x %}
        {% set ay = a_pose.y %}
        {% set ath = a_pose.theta %}
        {% set atype = act.ref.type|lower if act.ref.type else act.ref.__class__.__name__|lower %}
        {% set asub = act.ref.subtype|lower if act.ref.subtype is defined and act.ref.subtype and act.ref.subtype|lower != atype else None %}
        {% if asub %}
        {{ nodes_path }}["actuators"].setdefault("{{ atype }}", {}).setdefault("{{ asub }}", {})
        {{ poses_path }}["actuators"].setdefault("{{ atype }}", {}).setdefault("{{ asub }}", {})
        {{ nodes_path }}["actuators"]["{{ atype }}"]["{{ asub }}"].setdefault("{{ aid }}", {})
        {{ poses_path }}["actuators"]["{{ atype }}"]["{{ asub }}"]["{{ aid }}"] = {
        {% else %}
        {{ nodes_path }}["actuators"].setdefault("{{ atype }}", {})
        {{ poses_path }}["actuators"].setdefault("{{ atype }}", {})
        {{ nodes_path }}["actuators"]["{{ atype }}"].setdefault("{{ aid }}", {})
        {{ poses_path }}["actuators"]["{{ atype }}"]["{{ aid }}"] = {
        {% endif %}
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
            {% set ref = p.ref %}
            {% set cls = ref.class|lower %}
            {% set type = ref.type|lower if ref.type else ref.__class__.__name__|lower %}
            {% if ref.subtype is defined and ref.subtype %}
                {% set subtype = ref.subtype|lower %}
            {% else %}
                {% if cls == "composite" or nodeclass == "CompositePlacement" %}
                    {# For composites, fallback to type or class name #}
                    {% set subtype = ref.type|lower if ref.type else ref.__class__.__name__|lower %}
                {% else %}
                    {# For normal sensors/actuators, no subtype if not defined #}
                    {% set subtype = None %}
                {% endif %}
            {% endif %}
            {% set node_name = ref.name|lower %}
            {% set nodeclass = p.nodeclass %}
            {% set category = 
                "sensors" if cls == "sensor" else
                "actuators" if cls == "actuator" else
                "actors" if cls == "actor" else
                "composites" if nodeclass == "CompositePlacement" else
                "obstacles" %}
            {# Initialization of composites #}
            {% if category == "composites" %}
        {# Use type if available, otherwise fallback to subtype or class name #}
        {% set comp_key = type if type else (subtype if subtype else ref.__class__.__name__|lower) %}

        if "{{ comp_key }}" not in self.nodes["composites"]:
            self.nodes["composites"]["{{ comp_key }}"] = {}
            self.poses["composites"]["{{ comp_key }}"] = {}

        if "{{ inst }}" not in self.nodes["composites"]["{{ comp_key }}"]:
            # Initialize node + pose dicts if not existing
            self.nodes["composites"]["{{ comp_key }}"]["{{ inst }}"] = {
                "sensors": {},
                "actuators": {},
                "composites": {}
            }
            self.poses["composites"]["{{ comp_key }}"]["{{ inst }}"] = {
                "x": {{ p.pose.x }},
                "y": {{ p.pose.y }},
                "theta": {{ p.pose.theta }},
                "sensors": {},
                "actuators": {},
                "composites": {}
            }
                {% else %}
                {# Initialization of sensors, actuators, actors #}
                {% if type and subtype and subtype != type %}
        # Example path: sensors[rangefinder][sonar][so_1]
        if "{{ type }}" not in self.nodes["{{ category }}"]:
            self.nodes["{{ category }}"]["{{ type }}"] = {}
            self.poses["{{ category }}"]["{{ type }}"] = {}

        if "{{ subtype }}" not in self.nodes["{{ category }}"]["{{ type }}"]:
            self.nodes["{{ category }}"]["{{ type }}"]["{{ subtype }}"] = []
            self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"] = {}

        if "{{ inst }}" not in self.nodes["{{ category }}"]["{{ type }}"]["{{ subtype }}"]:
            self.nodes["{{ category }}"]["{{ type }}"]["{{ subtype }}"].append("{{ inst }}")
                {% elif type %}
        # Fallback path: sensors[microphone][mic_1]
        if "{{ type }}" not in self.nodes["{{ category }}"]:
            self.nodes["{{ category }}"]["{{ type }}"] = []
            self.poses["{{ category }}"]["{{ type }}"] = {}

        if "{{ inst }}" not in self.nodes["{{ category }}"]["{{ type }}"]:
            self.nodes["{{ category }}"]["{{ type }}"].append("{{ inst }}")
               {% else %}
        # Simple fallback for unnamed categories
        if "{{ node_name }}" not in self.nodes["{{ category }}"]:
            self.nodes["{{ category }}"]["{{ node_name }}"] = []
            self.poses["{{ category }}"]["{{ node_name }}"] = {}

        if "{{ inst }}" not in self.nodes["{{ category }}"]["{{ node_name }}"]:
            self.nodes["{{ category }}"]["{{ node_name }}"].append("{{ inst }}")
                {% endif %}
            {% endif %}
        
                # Define {{ inst }} node
        {% if category == "composites" %}
        {% set comp_key = type if type else (subtype if subtype else ref.__class__.__name__|lower) %}
        # Insert composite properties into nested structure
        self.nodes["composites"]["{{ comp_key }}"]["{{ inst }}"].update({
            "class": "composite",
            "type": "{{ type }}",
            "name": "{{ node_name }}",
            "pubFreq": {{ p.ref.pubFreq }},
            "properties": {
                {% set excluded = [
                    "class","type","subtype","shape","pubFreq","name","dataModel",
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
                            if k not in ["_tx_model","_tx_position","_tx_position_end","parent","ref"]
                            and v is not none -%}
                            "{{ k }}": {{ v|tojson }},
                        {%- endfor -%}
                        }
                    {%- else -%} {{ val|tojson }}
                    {%- endif -%},
                {% endfor %}
            },
            "initial_pose": {
                "x": {{ p.pose.x }},
                "y": {{ p.pose.y }},
                "theta": {{ p.pose.theta }}
            }
        })
        {% else %}
        # Define {{ inst }} node
        self.nodes["{{ inst }}"] = {
            "class": "{{ ref.class|lower if ref.class is defined and ref.class else ( 'composite' if p.nodeclass == 'CompositePlacement' else obj.__class__.__name__|lower ) }}",
            {% if type %}
            "type": "{{ type }}",
            {% endif %}
            {% if subtype %}
            "subtype": "{{ subtype }}",
            {% endif %}
            "name": "{{ node_name }}",
            "pubFreq": {{ p.ref.pubFreq }},
            "properties": {
                {% set excluded = [
                    "class","type","subtype","shape","pubFreq","name","dataModel",
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
                            if k not in ["_tx_model","_tx_position","_tx_position_end","parent","ref"]
                            and v is not none -%}
                            "{{ k }}": {{ v|tojson }},
                        {%- endfor -%}
                        }
                    {%- else -%} {{ val|tojson }}
                    {%- endif -%},
                {% endfor %}
            }
        }
        {% endif %}

        # Define {{ inst }} pose
        {% if category == "composites" %}
        {% set comp_key = type if type else (subtype if subtype else ref.__class__.__name__|lower) %}
        self.poses["{{ category }}"]["{{ comp_key }}"]["{{ inst }}"].update({
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        })
        {% else %}
            {% if node_name == "linearalarm" %}
        self.poses["{{ category }}"]["{{ type  }}"]["{{ subtype }}"]["{{ inst }}"] = {
            "start": {
                "x": {{ p.ref.shape.points[0].x }},
                "y": {{ p.ref.shape.points[0].y }}
            },
            "end": {
                "x": {{ p.ref.shape.points[1].x }},
                "y": {{ p.ref.shape.points[1].y }}
            }
        }
            {% elif type and subtype %}
        self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
            {% elif type %}
        self.poses["{{ category }}"]["{{ type }}"]["{{ inst }}"] = {
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
        {% endif %}
        self.tree[self.env_name.lower()].append("{{ inst }}")
        
        {% if p.nodeclass == "CompositePlacement" %}
        {% set comp_key = type if type else (subtype if subtype else ref.__class__.__name__|lower) %}
        {{ register_composite_children(
            "self.nodes['composites']['" ~ comp_key ~ "']['" ~ inst ~ "']",
            "self.poses['composites']['" ~ comp_key  ~ "']['" ~ inst ~ "']",
            p.ref,
            {'x': p.pose.x, 'y': p.pose.y, 'theta': p.pose.theta},
            inst
        ) }}
        {% endif %}
        # Define {{ inst }} subscriber
        {% set parent_tuple = (p.ref.parent.subtype, p.ref.parent.name) if p.ref.parent is defined else None %}
        {% set topic_base = topic_prefix(p.ref, parent_tuple) | trim %}
        self.{{ inst }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_base }}.{{ inst }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ inst }}": \
                self.node_pose_callback({
                    "class": "{{ ref.class|lower if ref.class is defined and ref.class else ( 'composite' if p.nodeclass == 'CompositePlacement' else obj.__class__.__name__|lower ) }}",  # e.g. sensor, actuator, composite, actor
                    "type": "{{ type if type else '' }}",
                    {% if subtype %}
                    "subtype": "{{ subtype if subtype else '' }}",
                    {% endif %}
                    "name": "{{ node_name }}",
                    "x": msg.x,
                    "y": msg.y,
                    "theta": msg.theta
                }{% if p.ref.parent is defined %}, parent_pose={
                    "x": {{ p.pose.x }},
                    "y": {{ p.pose.y }},
                    "theta": {{ p.pose.theta }}
                }{% endif %})
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

    def node_pose_callback(self, node: dict, parent_pose):
        return node_pose_callback(self.nodes, self.poses, self.log, node, parent_pose)

    def print_tf_tree(self):
        """Print a hierarchical TF tree of all nodes with poses."""

        def format_pose(p):
            """Return a formatted pose string."""
            if isinstance(p, dict):
                if "start" in p and "end" in p:
                    s, e = p["start"], p["end"]
                    return f"(start=({s['x']:.2f},{s['y']:.2f}) -> end=({e['x']:.2f},{e['y']:.2f}))"
                elif all(k in p for k in ["x", "y", "theta"]):
                    return f"(x={p['x']:.2f}, y={p['y']:.2f}, theta={p['theta']:.2f} deg)"
            return ""

        def is_pose(p):
            """Check if dict is a pose."""
            return isinstance(p, dict) and (
                all(k in p for k in ["x", "y", "theta"]) or ("start" in p and "end" in p)
            )

        def recurse(node_name, node_data, indent=0):
            pad = "    " * indent
            if is_pose(node_data):
                self.log.info(f"{pad}- {node_name} {format_pose(node_data)}")
                # Dive into children if any
                for k, v in node_data.items():
                    if isinstance(v, dict) and not is_pose(v):
                        recurse(k, v, indent + 1)
                return

            if isinstance(node_data, dict):
                # Consistent print order
                for section in ("composites", "actuators", "sensors"):
                    if section in node_data and node_data[section]:
                        self.log.info(f"{pad}- {section}")
                        for typ, group in node_data[section].items():
                            self.log.info(f"{pad}    - {typ}")
                            for inst, val in group.items():
                                if is_pose(val):
                                    self.log.info(f"{pad}        - {inst} {format_pose(val)}")
                                    recurse(inst, val, indent + 3)
                                elif isinstance(val, dict):
                                    recurse(inst, val, indent + 2)
                # Handle other keys
                for k, v in node_data.items():
                    if k not in ("composites", "actuators", "sensors"):
                        recurse(k, v, indent)

        # Entry point
        self.log.info(f"- {self.env_name}")
        for category, data in self.poses.items():
            if data:
                self.log.info(f"    - {category.capitalize()}")
                for name, val in data.items():
                    recurse(name, val, indent=2)

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
    # from omnisim.utils.visualizer import EnvVisualizer

    # vis = EnvVisualizer(node)
    # threading.Thread(target=node.start, daemon=True).start()
    # vis.render()
    try:
        node.start()
    except KeyboardInterrupt:
        node.log.info("Stopped by user.")
        node.stop()
