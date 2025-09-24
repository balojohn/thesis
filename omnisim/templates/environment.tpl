import sys, time, threading, logging, redis
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import math
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from ...utils.utils import *
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
        # Mount offsets (static, from DSL placements)
        self.mount_offsets = {}

        # Tree structure (who hosts what)
        self.tree = {}
        self.tree[self.env_name.lower()] = []
        
        {# ---- atomic entities directly in the env ---- #}
        {% for t in environment.things or [] %}
            {% set inst = t.instance_id if t.instance_id else t.ref.name|lower %}
            {% if t.ref.class == "Sensor" %}
        self.poses["sensors"]["{{ t.instance_id }}"] = {
            "x": {{ t.pose.x }},
            "y": {{ t.pose.y }},
            "theta": {{ t.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ t.instance_id }}")
            {% elif t.ref.class == "Actuator" %}
        
        self.poses["actuators"]["{{ t.instance_id }}"] = {
            "x": {{ t.pose.x }},
            "y": {{ t.pose.y }},
            "theta": {{ t.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ t.instance_id }}")
            {% endif %}
        {% endfor %}

        {% for a in environment.actors or [] %}
        {% set inst = a.instance_id if a.instance_id else a.ref.name|lower %}
        self.poses["actors"]["{{ inst }}"] = {
            "x": {{ a.pose.x }},
            "y": {{ a.pose.y }},
            "theta": {{ a.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ a.instance_id }}")
        {% endfor %}

        {% for o in environment.obstacles or [] %}
        {% set inst = o.instance_id if o.instance_id else o.ref.name|lower %}
        self.poses["obstacles"]["{{ inst }}"] = {
            "x": {{ o.pose.x }},
            "y": {{ o.pose.y }},
            "theta": {{ o.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ inst }}")
        {% endfor %}
        
        {# ---- composites with children ---- #}
        {% for c in environment.things if c.__class__.__name__ == "CompositePlacement" %}
            {% set inst = c.instance_id if c.instance_id else c.ref.name|lower %}
        self.poses["composites"]["{{ inst }}"] = {
            "x": {{ c.pose.x }},
            "y": {{ c.pose.y }},
            "theta": {{ c.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ inst }}")
        self.tree["{{ inst }}"] = []
            {% for child in c.sensors or [] %}
                {% set child_inst = child.instance_id if child.instance_id else child.ref.name|lower %}
        self.poses["sensors"]["{{ child_inst }}"] = {
            "x": {{ child.pose.x }},
            "y": {{ child.pose.y }},
            "theta": {{ child.pose.theta }}
        }
        self.tree["{{ inst }}"].append("{{ child_inst }}")
        self.mount_offsets["{{ child_inst }}"] = {
            "dx": {{ child.transformation.x }},
            "dy": {{ child.transformation.y }},
            "dtheta": {{ child.transformation.theta }}
        }
            {% endfor %}
            {% for child in c.actuators or [] %}
                {% set child_inst = child.instance_id if child.instance_id else child.ref.name|lower %}
        self.poses["actuators"]["{{ child_inst }}"] = {
            "x": {{ child.pose.x }},
            "y": {{ child.pose.y }},
            "theta": {{ child.pose.theta }}
        }
        self.tree["{{ inst }}"].append("{{ child_inst }}")
        self.mount_offsets["{{ child_inst }}"] = {
            "dx": {{ child.transformation.x }},
            "dy": {{ child.transformation.y }},
            "dtheta": {{ child.transformation.theta }}
        }
            {% endfor %}
            {% for child in c.composites or [] %}
                {% set child_inst = child.instance_id if child.instance_id else child.ref.name|lower %}
        self.poses["composites"]["{{ child_inst }}"] = {
            "x": {{ child.pose.x }},
            "y": {{ child.pose.y }},
            "theta": {{ child.pose.theta }}
        }
        self.tree["{{ inst }}"].append("{{ child_inst }}")
        self.mount_offsets["{{ child_inst }}"] = {
            "dx": {{ child.transformation.x }},
            "dy": {{ child.transformation.y }},
            "dtheta": {{ child.transformation.theta }}
        }
            {% endfor %}
        {% endfor %}            
        {% for t in environment.things or [] %}
            {# Always define a usable instance name #}
            {% set inst = t.instance_id if t.instance_id else t.ref.name|lower %}
            {# Resolve category #}
            {% if t.__class__.__name__ == "CompositePlacement" %}
                {% set category = "composites" %}
            {% elif t.ref.class == "Sensor" %}
                {% set category = "sensors" %}
            {% elif t.ref.class == "Actuator" %}
                {% set category = "actuators" %}
            {% else %}
                {% set category = "actors" %}
            {% endif %}
        self.{{ inst }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_prefix(t.ref) }}.{{ inst }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ inst }}": \
                self.node_pose_callback(
                    "{{ category }}",
                    {
                        "name": name,
                        "x": msg.x,
                        "y": msg.y,
                        "theta": msg.theta
                    }
                )
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
    # ---- Utility functions ----
    node_pose_callback = node_pose_callback
    composite_pose_callback = composite_pose_callback
    update_pan_tilt = update_pan_tilt

    def print_tf_tree(self):
        self.log.info(f"Transformation tree for {self.env_name}:")

        def recurse(node, indent=0):
            pose = None
            for cat, nodes in self.poses.items():
                if node in nodes:
                    pose = nodes[node]
                    break
            self.log.info("  " * indent + f"- {node} @ {pose}")
            if node in self.tree:
                for child in self.tree[node]:
                    recurse(child, indent + 1)

        # start from env root if available
        root = self.env_name.lower()
        if root in self.tree:
            recurse(root)
        else:
            # fallback: flat listing like your current code
            for category in ["sensors", "actuators", "actors", "composites", "obstacles"]:
                if self.poses[category]:
                    self.log.info(category.capitalize() + ":")
                    for name, pose in self.poses[category].items():
                        self.log.info(f"    {name} @ {pose}")

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
