# -*- coding: utf-8 -*-
import sys, threading, redis, subprocess, time, math, random
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate
{% if obj.__class__.__name__ != "CompositeThing" %}
from commlib.msg import PubSubMessage
{% endif %}
from omnisim.utils.geometry import PoseMessage
from omnisim.utils.utils import make_tf_matrix, apply_transformation
{# --- Import generated child nodes (for composites only) --- #}
{% if obj.__class__.__name__ == "CompositeThing" %}
    {% for posed_sensor in obj.sensors %}
from .{{ posed_sensor.ref.subtype|lower if posed_sensor.ref.subtype is defined else posed_sensor.ref.type|lower }} import {{ posed_sensor.ref.subtype|capitalize if posed_sensor.ref.subtype is defined else posed_sensor.ref.type|capitalize }}Node
    {% endfor %}
    {% for posed_actuator in obj.actuators %}
from .{{ posed_actuator.ref.subtype|lower if posed_actuator.ref.subtype is defined else posed_actuator.ref.type|lower }} import {{ posed_actuator.ref.subtype|capitalize if posed_actuator.ref.subtype is defined else posed_actuator.ref.type|capitalize }}Node
    {% endfor %}
    {% for posed_cthing in obj.composites %}
        {% if posed_cthing.ref.type is defined and posed_cthing.ref.type %}
            {% set comp_type = posed_cthing.ref.type|lower %}
        {% elif posed_cthing.ref.subtype is defined and posed_cthing.ref.subtype %}
            {% set comp_type = posed_cthing.ref.subtype|lower %}
        {% else %}
            {% set comp_type = posed_cthing.ref.__class__.__name__|lower %}
        {% endif %}
        {% if comp_type != obj.type|lower %}
from .{{ comp_type }} import {{ posed_cthing.ref.type|default(comp_type|capitalize, true) }}Node
        {% endif %}
    {% endfor %}
{% endif %}
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
{# Resolve object (Sensor, Actuator, Actor, Composite, Robot) --- #}
{% set parent_tuple = (obj.parent.subtype, obj.parent.name) if obj.parent is defined else None %}
{% set topic_base = topic_prefix(obj, parent=parent_tuple) | trim %}
{% set dtype_name = (obj.subtype if obj.subtype is defined else obj.type) + "Data" %}
{% set data_type = (dtype.types | selectattr("name", "equalto", dtype_name) | first) %}
{% set thing_name = (
    obj.subtype
    if obj.subtype is defined
    else (obj.type if obj.type is defined else obj.__class__.__name__)
) %}
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
{% if obj.__class__.__name__ != "CompositeThing" %}
{# --- generate message classes for this node --- #}
{% for e in publishers %}
class {{ e.msg.name }}(PubSubMessage):
  {% for prop in e.msg.properties | unique(attribute='name') %}
    {{ prop.name }}: {{ "float" if prop.type.name == "float" else "int" if prop.type.name == "int" else "bool" if prop.type.name == "bool" else "str" }}
  {% endfor %}
{% endfor %}
{% endif %}

class {{ thing_name }}Node(Node):
    def __init__(self, {{ id_field }}: str = "", parent_topic: str = "", *args, **kwargs):
        # --- Extract custom kwargs (not for commlib.Node) ---
        self._rel_pose = kwargs.pop("rel_pose", None)
        self._initial_pose = kwargs.pop("initial_pose", None)
        super().__init__(
            node_name="{{ thing_name.lower() }}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        base_topic = "{{ topic_base }}"
        full_topic_prefix = f"{parent_topic}.{base_topic}" if parent_topic else base_topic
        self.{{ id_field }} = {{ id_field }}
        self.pub_freq = {{ obj.pubFreq }}
        self.running = True
        # self.thread = None
        {% if obj.__class__.__name__ == "CompositeThing" %}
        self.children = {}
        {% endif %}
        {% for prop in data_type.properties %}
        # Default props
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

        # Pose initialization and transformation
        parent_pose = self._initial_pose or {"x": 0.0, "y": 0.0, "theta": 0.0}
        rel_pose = self._rel_pose or {"x": 0.0, "y": 0.0, "theta": 0.0}

        # Start from parent pose
        self.x = parent_pose["x"]
        self.y = parent_pose["y"]
        self.theta = parent_pose["theta"]
        
        # Apply relative transform if given
        if self._rel_pose:
            abs_pose = apply_transformation(
                {
                    "x": parent_pose["x"],
                    "y": parent_pose["y"],
                    "theta": parent_pose["theta"]
                },
                {
                    "x": rel_pose["x"],
                    "y": rel_pose["y"],
                    "theta": rel_pose["theta"]
                }
            )
            self.x = abs_pose["x"]
            self.y = abs_pose["y"]
            self.theta = abs_pose["theta"]

        {% if obj.__class__.__name__ == "CompositeThing" %}
        # Simple motion integration
        self._last_t = time.monotonic()
        self.vx = 0.10
        self.vy = 0.10
        self.omega = 10.0
        {% endif %}

        # Pose publisher (Sensors and Robots)
        self.pose_publisher = self.create_publisher(
            topic=f"{full_topic_prefix}.{{ '{self.' ~ id_field ~ '}' }}.pose",
            msg_type=PoseMessage
        )
        {% if obj.__class__.__name__ != "CompositeThing" %}
        {% for e in publishers %}
        # Data publisher for {{ e.msg.name }}
        self.data_publisher_{{ e.msg.name|lower|replace('message', '') }} = self.create_publisher(
            topic=f"{full_topic_prefix}.{{ '{self.' ~ id_field ~ '}' }}.data",
            msg_type={{ e.msg.name }}
        )
        {% endfor %}
        {% endif %}

        {% for posed_sensor in obj.sensors %}
            {% set node_type = posed_sensor.ref.subtype|capitalize if posed_sensor.ref.subtype is defined else posed_sensor.ref.type|capitalize %}
            {% set node_name = posed_sensor.ref.name.lower() %}
        # --- Sensor child: {{ node_type }} ---
        self.children["{{ node_name }}"] = {{ node_type }}Node(
            sensor_id=f"{{ node_name }}",
            parent_topic=f"{full_topic_prefix}.{self.{{ id_field }}}",
            rel_pose={  # relative to this composite
                'x': {{ posed_sensor.transformation.transformation.dx }},
                'y': {{ posed_sensor.transformation.transformation.dy }},
                'theta': {{ posed_sensor.transformation.transformation.dtheta }}
            },
            initial_pose={  # absolute of this composite
                'x': self.x,
                'y': self.y,
                'theta': self.theta
            }
        )
        {% endfor %}
        {% for posed_actuator in obj.actuators %}
            {% set node_type = posed_actuator.ref.subtype|capitalize if posed_actuator.ref.subtype is defined else posed_actuator.ref.type|capitalize %}
            {% set node_name = posed_actuator.ref.name.lower() %}
        # --- Actuator child: {{ node_type }} ---
        self.children["{{ node_name }}"] = {{ node_type }}Node(
            actuator_id=f"{{ node_name }}",
            parent_topic=f"{full_topic_prefix}.{self.{{ id_field }}}",
            rel_pose={
                'x': {{ posed_actuator.transformation.transformation.dx }},
                'y': {{ posed_actuator.transformation.transformation.dy }},
                'theta': {{ posed_actuator.transformation.transformation.dtheta }}
            },
            initial_pose={
                'x': self.x,
                'y': self.y,
                'theta': self.theta
            }
        )
        {% endfor %}
        {% for posed_cthing in obj.composites %}
            {% if obj.__class__.__name__ == "CompositeThing" %}
                {% set node_type = posed_cthing.ref.type %}
                {% set node_name = posed_cthing.ref.name.lower() %}
        # --- Composite child: {{ node_type }} ---
        self.children["{{ node_name }}"] = {{ node_type }}Node(
            composite_id=f"{{ node_name }}",
            parent_topic=f"{full_topic_prefix}.{self.{{ id_field }}}",
            rel_pose={
                'x': {{ posed_cthing.transformation.transformation.dx }},
                'y': {{ posed_cthing.transformation.transformation.dy }},
                'theta': {{ posed_cthing.transformation.transformation.dtheta }}
            },
            initial_pose={
                'x': self.x,
                'y': self.y,
                'theta': self.theta
            }
        )
            {% endif %}
        {% endfor %}
        print(f"[{self.__class__.__name__}] rel=({rel_pose['x']:.2f},{rel_pose['y']:.2f},{rel_pose['theta']:.2f}) "
          f"abs=({self.x:.2f},{self.y:.2f},{self.theta:.2f})")

    {% if obj.__class__.__name__ == "CompositeThing" %}
    def _integrate_motion(self):
        now = time.monotonic()
        dt = now - self._last_t
        self._last_t = now

        # Integrate translational motion in heading direction
        th_rad = math.radians(self.theta)
        self.x += self.vx * math.cos(th_rad) * dt
        self.y += self.vx * math.sin(th_rad) * dt
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
            {% if obj.__class__.__name__ == "CompositeThing" %}
            self._integrate_motion()
            {% endif %}
            msg_pose = PoseMessage(
                x=self.x,
                y=self.y,
                theta=self.theta
            )
            self.pose_publisher.publish(msg_pose)
            print(f"[{self.__class__.__name__}] Publishing pose to {self.pose_publisher.topic}: {msg_pose.model_dump()}")
            
            {% if obj.__class__.__name__ != "CompositeThing" %}
            {% for e in publishers %}
            msg_data = {{ e.msg.name }}(
                pubFreq=self.pub_freq,
                sensor_id=self.{{ id_field }},
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
            {% endif %}
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
    {{ id_field }} = sys.argv[1] if len(sys.argv) > 1 else "{{ thing_name.lower() }}_1"
    node = {{ thing_name }}Node({{ id_field }}={{ id_field }}, parent_topic="")
    try:
        node.start()
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()
        sys.exit(0)
