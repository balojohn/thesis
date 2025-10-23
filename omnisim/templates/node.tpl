# -*- coding: utf-8 -*-
import sys, threading, redis, subprocess, time, math, random
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate
{% if obj.__class__.__name__ != "CompositeThing" %}
from commlib.msg import PubSubMessage
{% endif %}
from omnisim.utils.geometry import (
    PoseMessage,
    {% if obj.__class__.__name__ == "CompositeThing" or obj.__class__.__name__ == "Human" %}
    VelocityMessage,
    {% endif %}
    make_tf_matrix,
    apply_transformation
)
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
    {# --- Parent extraction --- #}
    {% set has_parent = parent and parent|length == 2 %}
    {% set ptype = parent[0] if has_parent else None %}
    {% set pid = parent[1] if has_parent else None %}
    {# Case 1: Sensor in composite or atomic #}
    {% if cls == "sensor" %}
        {% if has_parent %}
            composite.{{ ptype }}.{{ pid }}.sensor.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% else %}
            sensor.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% endif %}
    {# Case 2: Actuator in composite or atomic #}
    {% elif cls == "actuator" %}
        {% if has_parent %}
            composite.{{ ptype }}.{{ pid }}.actuator.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% else %}
            actuator.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% endif %}
    {# Case 3: Actor in composite or atomic #}
    {% elif cls == "actor" %}
        {% if has_parent %}
            composite.{{ ptype }}.{{ pid }}.actor.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% else %}
            actor.{{ type_part }}{% if subtype and subtype != type_part %}.{{ subtype }}{% endif %}
        {% endif %}
    {# Case 4: CompositeThing #}
    {% elif obj.__class__.__name__ == "CompositeThing" %}
        {% if has_parent %}
            composite.{{ ptype }}.{{ pid }}.composite.{{ type_part }}
        {% else %}
            composite.{{ type_part }}
        {% endif %}
    {# Case 5: Generic fallback #}
    {% else %}
        composite.{{ type_part }}
    {% endif %}
{%- endmacro %}
{# --- Resolve canonical topic_base for this object --- #}
{% set cls = obj.class|lower %}
{% set type_part = obj.type|lower if obj.type is defined else obj.__class__.__name__|lower %}
{% set subtype = obj.subtype|lower if obj.subtype is defined else None %}

{% if cls == "sensor" %}
    {% set topic_base = "sensor." ~ type_part %}
    {% if subtype and subtype != type_part %}
        {% set topic_base = topic_base ~ "." ~ subtype %}
    {% endif %}
{% elif cls == "actuator" %}
    {% set topic_base = "actuator." ~ type_part %}
    {% if subtype and subtype != type_part %}
        {% set topic_base = topic_base ~ "." ~ subtype %}
    {% endif %}
{% elif cls == "actor" %}
    {% set topic_base = "actor." ~ type_part %}
{% elif obj.__class__.__name__ == "CompositeThing" %}
    {% set topic_base = "composite." ~ type_part %}
{% else %}
    {% set topic_base = "composite." ~ type_part %}
{% endif %}
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
        self.affection_handler = kwargs.pop("affection_handler", None)
        super().__init__(
            node_name="{{ thing_name.lower() }}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        self.node_class = "{{ cls }}"

        # --- Topic hierarchy setup ---
        base_topic = "{{ topic_base }}"
        self.parent_topic = parent_topic
        if parent_topic:
            # If this node is inside a composite, prepend the parent's topic
            full_topic_prefix = f"{parent_topic}.{base_topic}"
        else:
            # Top-level node (like Robot or top composite)
            full_topic_prefix = base_topic
        print(f"[{self.__class__.__name__}] parent_topic={parent_topic}, base_topic={base_topic}, full_topic_prefix={full_topic_prefix}")
        self.{{ id_field }} = {{ id_field }}
        self.pub_freq = {{ obj.pubFreq }}
        self.running = False
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

        # Pose initialization and transformation
        parent_pose = self._initial_pose or {"x": 0.0, "y": 0.0, "theta": 0.0}
        rel_pose = self._rel_pose or {"x": 0.0, "y": 0.0, "theta": 0.0}

        # Compute initial absolute pose (used as fixed reference)
        abs_pose = apply_transformation(parent_pose, rel_pose)
        self.abs_init_x = abs_pose["x"]
        self.abs_init_y = abs_pose["y"]
        self.abs_init_theta = abs_pose["theta"]

        # Current dynamic pose (will update with movement)
        self.x = self.abs_init_x
        self.y = self.abs_init_y
        self.theta = self.abs_init_theta
        # Track local independent rotation (used when composite follows parent + rotates itself)
        # --- Composite orientation tracking ---
        self.parent_theta = parent_pose["theta"]
        self.rel_theta = rel_pose["theta"]
        self.local_theta = 0.0  # independent rotation (servo)
        {% if obj.__class__.__name__ == "CompositeThing" or obj.__class__.__name__ == "Human" %}
        # === Motion control mode ===
        self.automated = {{ 'True' if obj.automated else 'False' }}
        self.vel_lin = 0.0
        self.vel_ang = 0.0
        # --- Unified targets (Point | Angle | Pose) ---
        self.targets = [
            {% for t in obj.targets %}
            {
                {% if t.point is not none %}
                "x": {{ t.point.x }}, "y": {{ t.point.y }}
                {% elif t.angle is not none %}
                "theta": {{ t.angle.theta }}
                {% endif %}
            },
            {% endfor %}
        ]
        self.current_target_idx = 0
        self.has_target = False
        self._last_t = time.monotonic()

        if not self.automated:
            self.vel_sub = self.create_subscriber(
                topic=f"{full_topic_prefix}.{self.{{ id_field }}}.cmd_vel",
                msg_type=VelocityMessage,
                on_message=lambda msg: self._on_velocity(msg)
            )
        {% endif %}
        
        # Subscribe to parent pose updates
        if parent_topic:
            self.parent_pose_sub = self.create_subscriber(
                topic=f"{parent_topic}.pose",
                msg_type=PoseMessage,
                on_message=lambda msg: self._update_parent_pose(msg)
            )

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
            parent_topic=f"{full_topic_prefix}.{{ '{self.' ~ id_field ~ '}' }}",
            rel_pose={  # relative to this composite
                'x': {{ posed_sensor.transformation.transformation.dx }},
                'y': {{ posed_sensor.transformation.transformation.dy }},
                'theta': {{ posed_sensor.transformation.transformation.dtheta }}
            },
            initial_pose={  # absolute (fixed) pose of parent
                'x': self._initial_pose["x"] if self._initial_pose else self.abs_init_x,
                'y': self._initial_pose["y"] if self._initial_pose else self.abs_init_y,
                'theta': self._initial_pose["theta"] if self._initial_pose else self.abs_init_theta
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
            initial_pose={  # absolute (fixed) pose of parent
                'x': self._initial_pose["x"] if self._initial_pose else self.abs_init_x,
                'y': self._initial_pose["y"] if self._initial_pose else self.abs_init_y,
                'theta': self._initial_pose["theta"] if self._initial_pose else self.abs_init_theta
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
            initial_pose={  # absolute (fixed) pose of parent
                'x': self._initial_pose["x"] if self._initial_pose else self.abs_init_x,
                'y': self._initial_pose["y"] if self._initial_pose else self.abs_init_y,
                'theta': self._initial_pose["theta"] if self._initial_pose else self.abs_init_theta
            }
        )
            {% endif %}
        {% endfor %}
        print(f"[{self.__class__.__name__}] rel=({rel_pose['x']:.2f},{rel_pose['y']:.2f},{rel_pose['theta']:.2f}) "
          f"abs=({self.x:.2f},{self.y:.2f},{self.theta:.2f})")

    {% if obj.__class__.__name__ == "CompositeThing" or obj.__class__.__name__ == "Human" %}
    def _on_velocity(self, msg):
        """Update velocity from external command."""
        self.vel_lin = msg.vel_lin
        self.vel_ang = msg.vel_ang
    
    def _next_poi(self):
        """Advance to the next POI cyclically."""
        if not self.pois:
            return None
        self.current_poi_idx = (self.current_poi_idx + 1) % len(self.pois)
        return self.pois[self.current_poi_idx]
    
    def _follow_targets(self, dt):
        """Generic motion toward linear or angular targets."""
        if not self.targets:
            return

        if not self.has_target:
            self.target = self.targets[self.current_target_idx]
            self.has_target = True

        t = self.target
        has_xy = "x" in t and "y" in t
        has_theta = "theta" in t

        # --- Translation targets (Point or Pose) ---
        if has_xy:
            dx, dy = t["x"] - self.x, t["y"] - self.y
            dist = math.hypot(dx, dy)
            if dist < 5.0:
                self.has_target = False
                self.current_target_idx = (self.current_target_idx + 1) % len(self.targets)
                return
            th_target = math.degrees(math.atan2(dy, dx))
            angle_diff = (th_target - self.theta + 180) % 360 - 180
            max_ang_speed = 60.0
            if abs(angle_diff) > 2.0:
                self.vel_ang = max(-max_ang_speed, min(max_ang_speed, angle_diff * 2.0))
            else:
                self.vel_ang = 0.0
            # Update orientation each step
            self.theta = (self.theta + self.vel_ang * dt) % 360.0
            self.vel_lin = 30.0 if abs(angle_diff) < 45 else 10.0
            th_rad = math.radians(self.theta)
            self.x += self.vel_lin * math.cos(th_rad) * dt
            self.y += self.vel_lin * math.sin(th_rad) * dt
        # --- Rotation-only targets (Angle or Pose) ---
        elif has_theta:
            # --- Local difference only ---
            diff = t["theta"] - self.local_theta
            diff = (diff + 180) % 360 - 180  # normalize

            max_ang_speed = 60.0
            self.vel_ang = max(-max_ang_speed, min(max_ang_speed, diff * 2.0))
            self.local_theta += self.vel_ang * dt

            # Normalize local_theta to [-180, 180]
            if self.local_theta > 180:
                self.local_theta -= 360
            elif self.local_theta < -180:
                self.local_theta += 360

            # --- Check completion (use normalized diff) ---
            if abs(diff) < 3.0:
                self.has_target = False
                self.current_target_idx = (self.current_target_idx + 1) % len(self.targets)
                return

            # --- Combine orientation properly ---
            self.theta = (self.parent_theta + self.rel_theta + self.local_theta) % 360.0
            
    {% endif %}
    def _update_parent_pose(self, msg):
        """
        Update this node's position based on parent pose updates.
        For composites like Pantilt, orientation (theta) remains independent.
        """
        parent_pose = {'x': msg.x, 'y': msg.y, 'theta': msg.theta}
        self._initial_pose = parent_pose
        abs_pose = apply_transformation(parent_pose, self._rel_pose)

        # Update position only
        self.x = abs_pose["x"]
        self.y = abs_pose["y"]

        # Always store parent rotation for composite composition
        self.parent_theta = parent_pose["theta"]
    
    {% if cls == "sensor" %}
    def simulate(self):
        return getattr(self, "_sim_data", {})
    {% endif %}

    def start(self):
        """Start this node and all its children (if composite)."""
        if self.running:
            return
        print(f"[{self.__class__.__name__}] Starting main loop...")

        # --- Initialize all publishers/subscribers BEFORE running Redis ---
        if not hasattr(self, "pose_publisher"):
            self.pose_publisher = self.create_publisher(
                topic=f"{self.full_topic_prefix}.{{ '{self.' ~ id_field ~ '}' }}.pose",
                msg_type=PoseMessage
            )

        {% if obj.__class__.__name__ != "CompositeThing" %}
        {% for e in publishers %}
        if not hasattr(self, "data_publisher_{{ e.msg.name|lower|replace('message', '') }}"):
            self.data_publisher_{{ e.msg.name|lower|replace('message', '') }} = self.create_publisher(
                topic=f"{self.full_topic_prefix}.{{ '{self.' ~ id_field ~ '}' }}.data",
                msg_type={{ e.msg.name }}
            )
        {% endfor %}
        {% endif %}

        # --- Connect to Redis transport ---
        threading.Thread(target=super().run, daemon=True).start()
        time.sleep(0.2)  # short delay so Redis connection stabilizes


        # --- Start loop ---
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # --- Start child nodes (for composites only) ---
        {% if obj.__class__.__name__ == "CompositeThing" %}
        if hasattr(self, "children"):
            for name, node in self.children.items():
                print(f"  -> Starting child {name}")
                node.start()
        {% endif %}


    def _run_loop(self):
        """Internal loop: publish pose (and data, if applicable)."""
        rate = Rate(self.pub_freq)
        self._last_t = time.monotonic()

        while self.running:
            {% if obj.__class__.__name__ == "CompositeThing" or obj.__class__.__name__ == "Human" %}
            now = time.monotonic()
            dt = now - self._last_t
            self._last_t = now

            if self.automated:
                self._follow_targets(dt)
            else:
                th_rad = math.radians(self.theta)
                self.x += self.vel_lin * math.cos(th_rad) * dt
                self.y += self.vel_lin * math.sin(th_rad) * dt
                self.theta = (self.theta + self.vel_ang * dt) % 360.0

            if hasattr(self, "children"):
                # Propagate only translation + parent orientation (not child's orientation)
                for name, child in self.children.items():
                    try:
                        parent_pose = PoseMessage(x=self.x, y=self.y, theta=self.theta)
                        child._update_parent_pose(parent_pose)
                    except Exception as e:
                        print(f"[{self.__class__.__name__}] Failed to update child {name}: {e}")
            {% endif %}
            # Publish pose
            msg_pose = PoseMessage(x=self.x, y=self.y, theta=self.theta)
            self.pose_publisher.publish(msg_pose)
            
            {% if cls == "sensor" %}
            # Update sensor data
            updated_props = self.simulate()
            extracted_value = None
            main_key = getattr(self, "subtype", getattr(self, "type", "temperature")).lower()

            # Handle the structure returned by affectability handlers
            if isinstance(updated_props, dict):
                # --- Case A: {'affections': {'temperature': 34.0}, 'env_properties': {...}} ---
                if "affections" in updated_props and isinstance(updated_props["affections"], dict):
                    inner = updated_props["affections"]
                    if main_key in inner and isinstance(inner[main_key], (int, float)):
                        extracted_value = inner[main_key]
                    else:
                        # fallback: first numeric value in the inner dict
                        for v in inner.values():
                            if isinstance(v, (int, float)):
                                extracted_value = v
                                break
                # --- Case B: {'temperature': 25.0} directly ---
                else:
                    for v in updated_props.values():
                        if isinstance(v, (int, float)):
                            extracted_value = v
                            break

            # Default fallback (ambient env property)
            if extracted_value is None:
                extracted_value = getattr(self, "properties", {}).get(main_key, 0.0)

            # Store in object for next publish
            setattr(self, main_key, extracted_value)
            {% endif %}

            {% if obj.__class__.__name__ != "CompositeThing" %}
            {% for e in publishers %}
            # Publish data message
            msg_data = {{ e.msg.name }}(
                pubFreq=self.pub_freq,
                sensor_id=self.{{ id_field }},
                type="{{ e.msg.name | replace('Message', 'Data') }}",
                {% if data_type %}
                {% for prop in data_type.properties %}
                {{ prop.name }}=self.{{ prop.name }},
                {% endfor %}
                {% endif %}
                # --- Inject affected variable dynamically ---
                **{main_key: extracted_value},
            )
            self.data_publisher_{{ e.msg.name|lower|replace('message', '') }}.publish(msg_data)
            {% endfor %}
            {% endif %}
            rate.sleep()

    def stop(self):
        """Stop this node and its children (if composite)."""
        if not getattr(self, "running", False):
            return
        print(f"[{self.__class__.__name__}] Stopping...")
        self.running = False

        # Stop child nodes first
        {% if obj.__class__.__name__ == "CompositeThing" %}
        if hasattr(self, "children"):
            for name, node in self.children.items():
                try:
                    node.stop()
                except Exception as e:
                    print(f"  [WARN] Failed to stop child {name}: {e}")
        {% endif %}

        # Wait for loop to end
        if hasattr(self, "_thread") and self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        # Stop commlib node safely
        try:
            super().stop()
        except Exception:
            pass

        print(f"[{self.__class__.__name__}] Stopped.")

if __name__ == '__main__':
    # --- Ensure Redis is running ---
    # redis_proc = None
    try:
        redis.Redis(host='localhost', port=6379).ping()
        print("[Redis] Connected successfully.")
    except redis.exceptions.ConnectionError:
        print("[Redis] Not running. Start Redis server first.")
        sys.exit(1)

    # --- Initialize node ---
    {{ id_field }} = sys.argv[1] if len(sys.argv) > 1 else "{{ thing_name.lower() }}_1"
    node = {{ thing_name }}Node({{ id_field }}={{ id_field }}, parent_topic="")

    try:
        node.start()
        while node.running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[System] Ctrl+C detected - shutting down...")
    finally:
        node.stop()
        # if redis_proc:
        #     redis_proc.terminate()
        print("[System] Exiting cleanly.")
        sys.exit(0)