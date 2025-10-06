import random
import math
import sys
import threading
import subprocess
import time
import redis
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate
from commlib.msg import PubSubMessage
{% set obj = thing|default(actor)|default(environment) %}
{% if obj.class == "Sensor" or obj.__class__.__name__ == "Robot" %}
from omnisim.utils.geometry import PoseMessage
{% endif %}
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
{# --- resolve object (Sensor, Actuator, Actor, Composite, Robot) --- #}
{% set topic_base = topic_prefix(obj) %}
{% set dtype_name = obj.name + "Data" %}
{% set data_type = (dtype.types | selectattr("name", "equalto", dtype_name) | first) %}
{# --- id_field depends on class --- #}
{% if obj.class == "Sensor" %}
  {% set id_field = "sensor_id" %}
{% elif obj.class == "Actuator" %}
  {% set id_field = "actuator_id" %}
{% else %}
  {% set id_field = "actor_id" %}
{% endif %}
{# --- default values for properties --- #}
{% set prop_values = {} %}
{% for prop in data_type.properties %}
{% if obj[prop.name] is defined %}
    {% set _ = prop_values.update({prop.name: obj[prop.name]}) %}
{% else %}
    {% set _ = prop_values.update({prop.name: None}) %}
{% endif %}
{% endfor %}
{# --- collect publishers for this object --- #}
{% set publishers = [] %}
{% for comm in comms.communications %}
  {% for e in comm.endpoints %}
    {% set _ = publishers.append(e) %}
    {% if e.__class__.__name__ == "publisher" %}
      {% set _ = publishers.append(e) %}
    {% endif %}
  {% endfor %}
{% endfor %}

# Path to your redis-server executable
REDIS_PATH = r"C:\redis\redis-server.exe"
def redis_start():
    print("[System] Starting Redis server...")
    try:
        proc = subprocess.Popen([REDIS_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
        if redis.Redis(host='localhost', port=6379).ping():
            print("[System] Redis is now running.")
            return proc
    except Exception as e:
        print(f"[ERROR] Could not start Redis: {e}")
        sys.exit(1)

{# --- generate message classes for this node --- #}
{% for e in publishers %}
class {{ e.msg.name }}(PubSubMessage):
  {% for prop in e.msg.properties | unique(attribute='name') %}
    {{ prop.name }}: {{ "float" if prop.type.name == "float" else "int" if prop.type.name == "int" else "bool" if prop.type.name == "bool" else "str" }}
  {% endfor %}
{% endfor %}
{#
{% set excluded = [
    "pubFreq",
    "type",
    "sensor_id",
    "actuator_id",
    "actor_id"
] %}
SIMULATED_PROPS = [
  {% for e in publishers %}
    {% for prop in e.msg.properties %}
      {% if prop.name not in excluded %}
  "{{ prop.name }}",
      {% endif %}
    {% endfor %}
  {% endfor %}
]
#}

class {{ obj.name }}Node(Node):
    def __init__(self, {{ id_field }}: str = "", initial_pose: dict | None = None, *args, **kwargs):
        self.pub_freq = {{ obj.pubFreq }}
        self.running = True
        self.thread = None
        self.{{ id_field }} = {{ id_field }}

        # Default props
        {% for prop in data_type.properties %}
        {% set val = prop_values.get(prop.name) %}
        {% if prop.type.name == "str" %}
        self.{{ prop.name }} = {{ '"' ~ (val | string | replace('"', '\\"')) ~ '"' if val is not none else '""' }}
        {% elif prop.type.name == "int" %}
        self.{{ prop.name }} = {{ val if val is not none else 0 }}
        {% elif prop.type.name == "Transformation" %}
        self.{{ prop.name }} = {
            "dx": {{ val.dx if val else 0.0 }},
            "dy": {{ val.dy if val else 0.0 }},
            "dtheta": {{ val.dtheta if val else 0.0 }}}
        {% else %}
        self.{{ prop.name }} = {{ val if val is not none else 0.0 }}
        {% endif %}
        {% endfor %}

        # Pose state
        self.x = (initial_pose or {}).get("x", 0.0)
        self.y = (initial_pose or {}).get("y", 0.0)
        self.theta = (initial_pose or {}).get("theta", 0.0)

        {% if obj.__class__.__name__ == "Robot" %}
        # Simple motion integration
        self._last_t = time.monotonic()
        self.vx = 0.10
        self.vy = 0.10
        self.omega = 10.0
        {% endif %}
        super().__init__(
            node_name="{{ obj.name.lower() }}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )

        {% if obj.class == "Sensor" or obj.__class__.__name__ == "Robot" %}
        # Pose publisher (Sensors and Robots)
        self.pose_publisher = self.create_publisher(
            topic=f"{{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}.pose",
            msg_type=PoseMessage
        )
        {% endif %}
        
        {% for e in publishers %}
        self.data_publisher = self.create_publisher(
            topic=f"{{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}",
            msg_type={{ e.msg.name }}
        )
        {% endfor %}
    {% if obj.__class__.__name__ == "Robot" %}
    def _integrate_motion(self):
        now = time.monotonic()
        dt = now - self._last_t
        self._last_t = now
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.theta = (self.theta + self.omega * dt) % 360.0
    {% endif %}

    {#
    def simulate(self):
        """
        Apply simple simulation logic to the node’s properties.
        This can be overridden or extended per node type.
        """
        # Create a local dict copy of properties
        props = {}
        {% for prop in data_type.properties %}
        props["{{ prop.name }}"] = self.{{ prop.name }}
        {% endfor %}

        # Example: add Gaussian noise to numeric properties
        for key, val in props.items():
            if isinstance(val, (int, float)):
                mean = val
                # If node has a 'noise' object (Gaussian(mean, std)), use that
                if hasattr(self, "noise") and hasattr(self.noise, "std"):
                    std = getattr(self.noise, "std", 0.1)
                    props[key] = mean + random.gauss(0, std)
                else:
                    props[key] = mean + random.gauss(0, 0.1)
        return props
    #}
    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        time.sleep(0.5)
        print(f"[{self.__class__.__name__}] Running with id={self.{{ id_field }}}")

        rate = Rate(self.pub_freq)
        while self.running:
            {% if obj.__class__.__name__ == "Robot" %}
            self._integrate_motion()
            {% endif %}
            {% if obj.class == "Sensor" or obj.__class__.__name__ == "Robot" %}
            self.pose_publisher.publish(PoseMessage(x=self.x, y=self.y, theta=self.theta))
            {% endif %}
            {% for e in publishers %}
            self.data_publisher.publish({{ e.msg.name }}(
                pubFreq=self.pub_freq,
                {{ id_field }}=self.{{ id_field }},
                type="{{ dtype_name }}",
                {% for prop in data_type.properties %}
                {{ prop.name }}=self.{{ prop.name }},
                {% endfor %}
            ))
            {% endfor %}
            rate.sleep()

    def stop(self):
        print(f"[{self.__class__.__name__}] stopping...")
        self.running = False
        try:
            super().stop()
        except Exception as e:
            print(f"[{self.__class__.__name__}] stop error: {e}")

if __name__ == '__main__':
    redis_start()
    {{ id_field }} = sys.argv[1] if len(sys.argv) > 1 else "{{ obj.name.lower() }}_1"
    node = {{ obj.name }}Node({{ id_field }}={{ id_field }})
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()
        sys.exit(0)
