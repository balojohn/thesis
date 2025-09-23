import sys, time, threading, logging, redis
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import math
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from ...utils.utils import *
from ...utils.geometry import PoseMessage
{# --- imports for messages actually used in this env --- #}
{% set ns = namespace(imported=[]) %}
{% set placements = (environment.things or []) + (environment.actors or []) + (environment.composites or []) %}
{% for p in placements %}
  {% set ref = p.ref %}
  {% set subclass = ref.__class__.__name__ | lower %}
  {% set type_seg = ('.' ~ (ref.type | lower)) if (ref.type is defined and ref.type) else '' %}
  {% set base_default = subclass ~ type_seg %}
  {% set base = p.poseTopic if p.poseTopic else base_default %}
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
            {% if t.ref.class == "Sensor" %}
        self.poses["sensors"]["{{ t.ref.name|lower }}"] = {
            "x": {{ t.pose.x }},
            "y": {{ t.pose.y }},
            "theta": {{ t.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ t.ref.name|lower }}")
            {% elif t.ref.class == "Actuator" %}
        
        self.poses["actuators"]["{{ t.ref.name|lower }}"] = {
            "x": {{ t.pose.x }},
            "y": {{ t.pose.y }},
            "theta": {{ t.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ t.ref.name|lower }}")
            {% endif %}
        {% endfor %}

        {% for a in environment.actors or [] %}
        self.poses["actors"]["{{ a.ref.name|lower }}"] = {
            "x": {{ a.pose.x }},
            "y": {{ a.pose.y }},
            "theta": {{ a.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ a.ref.name|lower }}")
        {% endfor %}

        {% for o in environment.obstacles or [] %}
        self.poses["obstacles"]["{{ o.ref.name|lower }}"] = {
            "x": {{ o.pose.x }},
            "y": {{ o.pose.y }},
            "theta": {{ o.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ o.ref.name|lower }}")
        {% endfor %}
        
        {# ---- composites with children ---- #}
        {% for c in environment.things if c.__class__.__name__ == "CompositePlacement" %}
        self.poses["composites"]["{{ c.ref.name|lower }}"] = {
            "x": {{ c.pose.x }},
            "y": {{ c.pose.y }},
            "theta": {{ c.pose.theta }}
        }
        self.tree[self.env_name.lower()].append("{{ c.ref.name|lower }}")
        self.tree["{{ c.ref.name|lower }}"] = []
            {% for child in c.sensors or [] %}
        self.poses["sensors"]["{{ child.ref.name|lower }}"] = {
            "x": {{ child.pose.x }},
            "y": {{ child.pose.y }},
            "theta": {{ child.pose.theta }}
        }
        self.tree["{{ c.ref.name|lower }}"].append("{{ child.ref.name|lower }}")
        self.mount_offsets["{{ child.ref.name|lower }}"] = {
            "dx": {{ child.transformation.x }},
            "dy": {{ child.transformation.y }},
            "dtheta": {{ child.transformation.theta }}
        }
            {% endfor %}
            {% for child in c.actuators or [] %}
        self.poses["actuators"]["{{ child.ref.name|lower }}"] = {
            "x": {{ child.pose.x }},
            "y": {{ child.pose.y }},
            "theta": {{ child.pose.theta }}
        }
        self.tree["{{ c.ref.name|lower }}"].append("{{ child.ref.name|lower }}")
        self.mount_offsets["{{ child.ref.name|lower }}"] = {
            "dx": {{ child.transformation.x }},
            "dy": {{ child.transformation.y }},
            "dtheta": {{ child.transformation.theta }}
        }
            {% endfor %}
            {% for child in c.composites or [] %}
        self.poses["composites"]["{{ child.ref.name|lower }}"] = {
            "x": {{ child.pose.x }},
            "y": {{ child.pose.y }},
            "theta": {{ child.pose.theta }}
        }
        self.tree["{{ c.ref.name|lower }}"].append("{{ child.ref.name|lower }}")
        self.mount_offsets["{{ child.ref.name|lower }}"] = {
            "dx": {{ child.transformation.x }},
            "dy": {{ child.transformation.y }},
            "dtheta": {{ child.transformation.theta }}
        }
            {% endfor %}
        {% endfor %}            
        {% for t in environment.things or [] %}
            {% set inst = t.instance_id if t.instance_id %}
            {% set category =
                "sensors" if t.ref.class == "Sensor"
                else "actuators" if t.ref.class == "Actuator"
                else "composites" if t.ref.__class__.__name__ == "CompositeThing"
                else "actors"
            %}
            {% set prefix =
                ("sensor." + t.ref.__class__.__name__|lower)
                if t.ref.class == "Sensor"
                else ("actuator." + t.ref.__class__.__name__|lower)
                if t.ref.class == "Actuator"
                else ("composite." + t.ref.name|lower)
                if t.ref.__class__.__name__ == "CompositeThing"
                else ("actor." + t.ref.__class__.__name__|lower)
            %}
            {% set type_seg = ("." + t.ref.type|lower) if t.ref.type is defined and t.ref.type else "" %}

        self.{{ inst }}_pose_sub = self.create_subscriber(
            topic=f"{{ prefix }}{{ type_seg }}.{{ inst }}.pose",
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
