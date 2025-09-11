import sys, time, threading, logging, redis
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
{# --- imports for messages actually used in this env --- #}
{% set ns = namespace(imported=[]) %}
{% set placements = (environment.things or []) + (environment.actors or []) %}
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
            "obstacles": {}
        }
        {% for t in environment.things or [] %}
            {% if t.ref.class == "Sensor" %}
        self.poses["sensors"]["{{ t.ref.name|lower }}"] = {
            "x": {{ t.pose.x }},
            "y": {{ t.pose.y }},
            "theta": {{ t.pose.theta }}
        }
            {% elif t.ref.class == "Actuator" %}
        self.poses["actuators"]["{{ t.ref.name|lower }}"] = {
            "x": {{ t.pose.x }},
            "y": {{ t.pose.y }},
            "theta": {{ t.pose.theta }}
        }
            {% endif %}
        {% endfor %}
        {% for a in environment.actors or [] %}
        self.poses["actors"]["{{ a.ref.name|lower }}"] = {
            "x": {{ a.pose.x }},
            "y": {{ a.pose.y }},
            "theta": {{ a.pose.theta }}
        }
        {% endfor %}
        {% for o in environment.obstacles or [] %}
        self.poses["obstacles"]["{{ o.ref.name|lower }}"] = {
            "x": {{ o.pose.x }},
            "y": {{ o.pose.y }},
            "theta": {{ o.pose.theta }}
        }
        {% endfor %}

    def print_tf_tree(self):
        self.log.info(f"Transformation tree for {self.env_name}:")

        if self.poses["sensors"]:
            self.log.info("Sensors:")
            for name, pose in self.poses["sensors"].items():
                self.log.info(f"    {name} @ {pose}")

        if self.poses["actuators"]:
            self.log.info("Actuators:")
            for name, pose in self.poses["actuators"].items():
                self.log.info(f"    {name} @ {pose}")

        if self.poses["actors"]:
            self.log.info("Actors:")
            for name, pose in self.poses["actors"].items():
                self.log.info(f"    {name} @ {pose}")

        if self.poses["obstacles"]:
            self.log.info("Obstacles:")
            for name, pose in self.poses["obstacles"].items():
                self.log.info(f"    {name} @ {pose}")

    def start(self):
        # Launch commlib internal loop in a background thread
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        self.log.info("Running. Press Ctrl+C to stop.")
        try:
            while True:
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
    node.print_tf_tree()
    try:
        node.start()
    except KeyboardInterrupt:
        node.log.info("Stopped by user.")
        node.stop()
