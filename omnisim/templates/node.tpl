import sys, threading, redis, subprocess, time, math, random
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate
from commlib.msg import PubSubMessage
{#{% set obj = thing|default(actor)|default(environment) %}#}
{% if obj.class == "Sensor" or obj.__class__.__name__ == "CompositeThing" %}
from omnisim.utils.geometry import PoseMessage
{% endif %}
{% macro topic_prefix(obj, parent_id=None) -%}
    {% set cls = obj.class|lower %}
    {% set name = obj.name|lower %}
    {% if obj.class == "Sensor" %}
        {% if parent_id %}
            composite.{{ parent_id }}.{{ name }}
        {% else %}
            sensor.{{ obj.type|lower }}.{{ name }}
        {% endif %}
    {% elif obj.class == "Actuator" %}
        {% if parent_id %}
            composite.{{ parent_id }}.{{ name }}
        {% else %}
            actuator.{{ obj.type|lower }}.{{ name }}
        {% endif %}
    {% elif obj.__class__.__name__ == "CompositeThing" %}
        {% if parent_id %}
            composite.{{ parent_id }}.{{ name }}
            # composite.robot.{{ parent_id }}.{{ name }}
        {% else %}
            composite.{{ name }}
        {% endif %}
    {% else %}
        composite.{{ name }}
    {% endif %}
{%- endmacro %}
{# Resolve object (Sensor, Actuator, Actor, Composite, Robot) --- #}
{% set topic_base = topic_prefix(obj, parent_id=obj.parent_id if obj.parent_id is defined else None) | trim %}
{% set dtype_name = obj.name + "Data" %}
{% set data_type = (dtype.types | selectattr("name", "equalto", dtype_name) | first) %}
{# Define id_field depending on class #}
{% if obj.class == "Sensor" %}
  {% set id_field = "sensor_id" %}
{% elif obj.class == "Actuator" %}
  {% set id_field = "actuator_id" %}
{% elif obj.class == "Actor" %}
  {% set id_field = "actor_id" %}
{% elif obj.__class__.__name__ == "CompositeThing" %}
  {% set id_field = "composite_id" %}
{% endif %}
{# Default values for properties taken from Model #}
{% set prop_values = {} %}
{% set data_type = (dtype.types | selectattr("name", "equalto", dtype_name) | first) %}
{% if data_type %}
  {% for prop in data_type.properties %}
      {% set _ = prop_values.update({prop.name: obj[prop.name]}) %}
  {% endfor %}
{% else %}
  {# No data type found (likely a composite/robot) — skip property mapping #}
  {% set data_type = None %}
{% endif %}
{# Collect publishers for this object --- #}
{% set publishers = [] %}
{% for comm in comms.communications %}
  {% for e in comm.endpoints %}
    {% set _ = publishers.append(e) %}
    {% if e.__class__.__name__ == "publisher" %}
      {% set _ = publishers.append(e) %}
    {% endif %}
  {% endfor %}
{% endfor %}
{# --- Import generated child nodes (for composites only) --- #}
{% if obj.__class__.__name__ == "CompositeThing" %}
    {% for posed_sensor in obj.sensors %}
from .{{ posed_sensor.ref.name.lower() }} import {{ posed_sensor.ref.name }}Node
    {% endfor %}
    {% for posed_actuator in obj.actuators %}
from .{{ posed_actuator.ref.name.lower() }} import {{ posed_actuator.ref.name }}Node
    {% endfor %}
    {% for posed_cthing in obj.composites %}
from .{{ posed_cthing.ref.name.lower() }} import {{ posed_cthing.ref.name }}Node
    {% endfor %}
{% endif %}

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
class {{ obj.name }}Node(Node):
    def __init__(self, {{ id_field }}: str = "", *args, **kwargs):
        # Remove already existing keys
        {#{% if obj.__class__.__name__ in ["CompositeThing", "Robot"] %} #}
        kwargs.pop("{{ id_field }}", None)
        kwargs.pop("initial_pose", None)
        {# {% endif %} #}
        super().__init__(
            node_name="{{ obj.name.lower() }}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        self.{{ id_field }} = {{ id_field }}
        self.pub_freq = {{ obj.pubFreq }}
        self.running = True
        # self.thread = None
        {% if obj.__class__.__name__ == "CompositeThing" %}
        self.children = {}
        {% endif %}
        # Default props
        {% for prop in data_type.properties %}
        {% set val = prop_values.get(prop.name) %}
        {% if prop.type.name == "str" %}
        self.{{ prop.name }} = {{ '"' ~ (val | string | replace('"', '\\"')) ~ '"' if val is not none else '""' }}
        {% elif prop.type.name == "int" %}
        self.{{ prop.name }} = {{ val if val is not none else 0 }}
        {% elif prop.type.name == "Transformation" %}
        self.{{ prop.name }} = {
            "dx": {{ val.dx if val }},
            "dy": {{ val.dy if val }},
            "dtheta": {{ val.dtheta if val }}}
        {% else %}
        self.{{ prop.name }} = {{ val if val is not none }}
        {% endif %}
        {% endfor %}

        # Pose state
        self.x = kwargs.get("initial_pose", {}).get("x", 0.0)
        self.y = kwargs.get("initial_pose", {}).get("y", 0.0)
        self.theta = kwargs.get("initial_pose", {}).get("theta", 0.0)

        {% if obj.__class__.__name__ == "Robot" %}
        # Simple motion integration
        self._last_t = time.monotonic()
        self.vx = 0.10
        self.vy = 0.10
        self.omega = 10.0
        {% endif %}

        {%- if obj.class == "Sensor" or obj.__class__.__name__ == "CompositeThing" %}
        # Pose publisher (Sensors and Robots)
        self.pose_publisher = self.create_publisher(
            topic=f"{{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}.pose",
            msg_type=PoseMessage
        )
        {% endif %}
        
        {% for e in publishers %}
        # Data publisher for {{ e.msg.name }}
        self.data_publisher_{{ e.msg.name|lower|replace('message', '') }} = self.create_publisher(
            topic=f"{{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}.{{ e.msg.name|lower|replace('message','') }}.data",
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
    {% for posed_sensor in obj.sensors %}
        self.children["{{ posed_sensor.ref.name.lower() }}"] = {{ posed_sensor.ref.name }}Node(
            sensor_id=f"{self.{{ id_field }}}_{{ posed_sensor.ref.name.lower() }}",
            initial_pose={
                'x': {{ posed_sensor.transformation.transformation.dx }},
                'y': {{ posed_sensor.transformation.transformation.dy }},
                'theta': {{ posed_sensor.transformation.transformation.dtheta }}
            }
        )
    {% endfor %}
    {% for posed_actuator in obj.actuators %}
        self.children["{{ posed_actuator.ref.name.lower() }}"] = {{ posed_actuator.ref.name }}Node(
            actuator_id=f"{self.{{ id_field }}}_{{ posed_actuator.ref.name.lower() }}",
            initial_pose={
                'x': {{ posed_actuator.transformation.transformation.dx }},
                'y': {{ posed_actuator.transformation.transformation.dy }},
                'theta': {{ posed_actuator.transformation.transformation.dtheta }}
            }
        )
    {% endfor %}
    {% for posed_cthing in obj.composites %}
        {% if obj.__class__.__name__ == "CompositeThing" %}
        # --- Children ---
        self.children["{{ posed_cthing.ref.name.lower() }}"] = {{ posed_cthing.ref.name }}Node(
            {{ id_field }}=f"{self.{{ id_field }}}_{{ posed_cthing.ref.name.lower() }}"
        )
        {% endif %}
    {% endfor %}

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
        {% if obj.__class__.__name__ == "CompositeThing" %}
        # --- Start child nodes (if any) ---
        if hasattr(self, "children") and self.children:
            for name, node in self.children.items():
                print(f"  -> starting child {name}")
                node.running = True
                threading.Thread(target=node.start, daemon=True).start()
        {% endif %}

        rate = Rate(self.pub_freq)
        while self.running:
            {% if obj.__class__.__name__ == "Robot" %}
            self._integrate_motion()
            {% endif %}
            {% if obj.class == "Sensor" or obj.__class__.__name__ == "CompositeThing" %}
            msg_pose = PoseMessage(
                x=self.x,
                y=self.y,
                theta=self.theta
            )
            self.pose_publisher.publish(msg_pose)
            print(f"[{self.__class__.__name__}] Publishing pose to {self.pose_publisher.topic}: {msg_pose.model_dump()}")
            {% endif %}
            {% for e in publishers %}
            msg_data = {{ e.msg.name }}(
                pubFreq=self.pub_freq,
                _id=self.{{ id_field }},
                type="{{ e.msg.name | replace('Message', 'Data') }}",
                {% if data_type %}
                {% for prop in data_type.properties %}
                {{ prop.name }}=self.{{ prop.name }},
                {% endfor %}
                {% endif %}
            )
            self.data_publisher_{{ e.msg.name|lower|replace('message', '') }}.publish(msg_data)
            print(f"[{self.__class__.__name__}] Publishing data to {self.data_publisher_{{ e.msg.name|lower|replace('message', '') }}.topic}: {msg_data.model_dump()}")
            {% endfor %}
            rate.sleep()

    def stop(self):
        print(f"[{self.__class__.__name__}] stopping...")
        self.running = False

        {% if obj.__class__.__name__ in ["CompositeThing", "Robot"] %}
        # Stop child nodes (if any)
        if hasattr(self, "children") and self.children:
            for name, node in self.children.items():
                try:
                    print(f"  -> stopping child {name}")
                    node.stop()
                    if hasattr(node, "thread") and node.thread:
                        node.thread.join(timeout=1.0)
                except Exception as e:
                    print(f"  !! failed to stop child {name}: {e}")
        {% endif %}
        # Stop this node's own commlib loop
        try:
            super().stop()
        except Exception as e:
            print(f"[{self.__class__.__name__}] stop error: {e}")
        
        print(f"[{self.__class__.__name__}] Stopped.")

if __name__ == '__main__':
    redis_start()
    {{ id_field }} = sys.argv[1] if len(sys.argv) > 1 else "{{ obj.name.lower() }}_1"
    node = {{ obj.name }}Node({{ id_field }}={{ id_field }})
    try:
        node.start()
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()
        sys.exit(0)
