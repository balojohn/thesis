import sys, time, threading, logging, redis, math
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from omnisim.utils.visualizer import EnvVisualizer
from omnisim.utils.geometry import node_pose_callback
# Affection handlers
from omnisim.utils.affections import check_affectability
{# KEY FIX: Store ORIGINAL values before lowercasing #}
{% macro camelcase(name) -%}
{%- set parts = name.split('_') -%}
{%- if parts | length == 1 -%}
{{ name }}
{%- else -%}
{{ parts | map('capitalize') | join('') | replace(' ', '') }}
{%- endif -%}
{%- endmacro %}
# Generated node classes
{% set placements = (environment.things or []) + (environment.composites or []) %}
{% for p in placements %}
    {% set ref = p.ref %}
    {% set cls = ref.class|lower %}
    {% set type_orig = ref.type if ref.type else ref.__class__.__name__ %}
    {% set type = type_orig|lower %}
    {% set subtype_orig = ref.subtype if ref.subtype is defined and ref.subtype else None %}
    {% set subtype = subtype_orig|lower if subtype_orig else None %}
    {% set node_classname = camelcase(subtype_orig) if subtype_orig else camelcase(type_orig) %}
    {% if cls == "sensor" %}
from omnisim.generated_files.things.{{ subtype if subtype else type }} import {{ node_classname }}Node, {{ node_classname }}Message, PoseMessage
    {% else %}
from omnisim.generated_files.things.{{ subtype if subtype else type }} import {{ node_classname }}Node, PoseMessage
    {% endif %}
{% endfor %}
{% macro topic_prefix(obj, parents=None) -%}
    {# Normalize parents input: ensure it's a list of (ptype, pid) tuples #}
    {% if parents is none %}
        {% set parents = [] %}
    {% elif parents is mapping or parents is string %}
        {% set parents = [] %}
    {% elif parents is sequence and parents and parents[0] is sequence %}
        {# already list of tuples #}
        {% set parents = parents %}
    {% elif parents is sequence and parents|length == 2 and parents[0] is string %}
        {% set parents = [parents] %}
    {% else %}
        {% set parents = [] %}
    {% endif %}

    {% set cls = obj.class|lower %}
    {% set type_part = obj.type|lower if obj.type is defined else obj.__class__.__name__|lower %}
    {% set subtype = obj.subtype|lower if obj.subtype is defined else None %}

    {# Build parent chain parts #}
    {% set parts = [] %}
    {% for pair in parents %}
        {% if pair|length == 2 %}
            {% set ptype, pid = pair[0], pair[1] %}
            {% set _ = parts.append("composite." ~ ptype ~ "." ~ pid) %}
        {% endif %}
    {% endfor %}

    {# Append current object class/type/subtype #}
    {% if cls == "sensor" %}
        {% set _ = parts.append("sensor." ~ type_part ~ ('.' ~ subtype if subtype and subtype != type_part else '')) %}
    {% elif cls == "actuator" %}
        {% set _ = parts.append("actuator." ~ type_part ~ ('.' ~ subtype if subtype and subtype != type_part else '')) %}
    {% elif obj.__class__.__name__ == "CompositeThing" %}
        {% set _ = parts.append("composite." ~ type_part) %}
    {% elif cls == "actor" %}
        {% set _ = parts.append("actor." ~ type_part ~ ('.' ~ subtype if subtype and subtype != type_part else '')) %}
    {% endif %}

    {{ parts | join('.') }}
{%- endmacro %}
{% macro render_properties(obj) -%}
    "properties": {
                {% set excluded = [
                    "class","type","subtype","shape","pubFreq","name","dataModel",
                    "_tx_position","_tx_model","_tx_position_end","parent",
                    "actuators","sensors","composites"
                ] %}
                {% for attr, val in obj.__dict__.items()
                if attr not in excluded and val is not none %}
                "{{ attr }}":
                    {%- if val is number -%} {{ val }}
                    {%- elif val is string -%} "{{ val }}"
                    {%- elif val.__class__.__name__ in [
                        "Constant","Linear","Quadratic","Exponential","Logarithmic",
                        "Gaussian","Uniform","CustomNoise"
                    ] -%}
                        {
                        {%- for k,v in val.__dict__.items()
                            if k not in ["_tx_model","_tx_position","_tx_position_end","parent","ref"]
                            and v is not none -%}
                            "{{ k }}": {{ v|tojson }},
                        {%- endfor -%}
                        }
                    {%- elif val.__class__.__name__ == "list" and val and
                    val[0].__class__.__name__ in ["TargetPose","Point","Angle","Pose"] -%}
                    [
                    {%- for tp in val -%}
                        {%- if tp.__class__.__name__ == "TargetPose" -%}
                            {%- if tp.point is defined and tp.point is not none -%}
                                {"x": {{ tp.point.x }}, "y": {{ tp.point.y }}}
                            {%- elif tp.angle is defined and tp.angle is not none -%}
                                {"angle": {{ tp.angle.value }}}
                            {%- endif -%}
                        {%- elif tp.__class__.__name__ == "Point" -%}
                            {"x": {{ tp.x }}, "y": {{ tp.y }}}
                        {%- elif tp.__class__.__name__ == "Angle" -%}
                            {"angle": {{ tp.value }}}
                        {%- elif tp.__class__.__name__ == "Pose" -%}
                            {"x": {{ tp.x }}, "y": {{ tp.y }}, "theta": {{ tp.theta }}}
                        {%- endif -%}
                        {%- if not loop.last %}, {% endif %}
                    {%- endfor -%}
                    ]
                    {%- else -%} {{ val|tojson }}
                    {%- endif -%},
                {% endfor %}
            }
{%- endmacro %}
{% macro render_shape(shape) -%}
"type": "{{ shape.__class__.__name__ }}",
        {% if shape.__class__.__name__ == "Rectangle" %}
            "width": {{ shape.width }},
            "length": {{ shape.length }}
        {% elif shape.__class__.__name__ == "Square" %}
            "length": {{ shape.length }}
        {% elif shape.__class__.__name__ == "Circle" %}
            "radius": {{ shape.radius }}
        {% elif shape.__class__.__name__ == "ArbitraryShape" %}
            "points": [
                {% for pt in shape.points %}
                {"x": {{ pt.x }}, "y": {{ pt.y }}},
                {% endfor %}
            ]
        {% endif %}
{%- endmacro %}
{# --- recursively register composite children --- #}
{% macro register_composite_children(nodes_path, poses_path, parent_ref, parent_pose, parent_id) %}
    {% set px, py, pth = parent_pose.x, parent_pose.y, parent_pose.theta %}

    {# === Child composites === #}
    {% for comp in parent_ref.composites %}
        {% set cname = comp.ref.name|lower %}
        {% set cid = cname %}
        {% set dx, dy, dth = comp.transformation.transformation.dx, comp.transformation.transformation.dy, comp.transformation.transformation.dtheta %}
        {% set abs_pose = apply_transformation(
            {'x': px, 'y': py, 'theta': pth},
            {'x': dx, 'y': dy, 'theta': dth},
            parent_shape=parent_ref.shape.__dict__ if parent_ref.shape is defined else None,
            child_shape=comp.ref.shape.__dict__ if comp.ref.shape is defined else None
        ) %}
        {% set cx, cy, cth = abs_pose.x, abs_pose.y, abs_pose.theta %}
        {% set ctype = (comp.ref.type|lower if comp.ref.type
                       else (comp.ref.subtype|lower if comp.ref.subtype
                       else comp.ref.__class__.__name__|lower)) %}

        # --- composite {{ cid }} ---
        {{ nodes_path }}["composites"].setdefault("{{ ctype }}", {})
        {{ poses_path }}["composites"].setdefault("{{ ctype }}", {})

        {{ nodes_path }}["composites"]["{{ ctype }}"]["{{ cid }}"] = {
            "class": "composite",
            "type": "{{ ctype }}",
            "name": "{{ cid }}",
            "sensors": {},
            "actuators": {},
            "composites": {}
        }
        {{ poses_path }}["composites"]["{{ ctype }}"]["{{ cid }}"] = {
            "rel_pose": {"x": {{ dx }}, "y": {{ dy }}, "theta": {{ dth }}},
            "sensors": {},
            "actuators": {},
            "composites": {}
        }

        {% if comp.ref.shape is defined %}
        shape_data = {
            {{ render_shape(comp.ref.shape) }}
        }
        {{ nodes_path }}["composites"]["{{ ctype }}"]["{{ cid }}"]["shape"] = shape_data
        {{ poses_path }}["composites"]["{{ ctype }}"]["{{ cid }}"]["shape"] = shape_data
        {% endif %}

        {{ register_composite_children(
            nodes_path ~ "['composites']['" ~ ctype ~ "']['" ~ cid ~ "']",
            poses_path ~ "['composites']['" ~ ctype ~ "']['" ~ cid ~ "']",
            comp.ref,
            {'x': cx, 'y': cy, 'theta': cth},
            cid
        ) }}
    {% endfor %}

    {# === Atomic children (sensors + actuators) === #}
    {% for child in parent_ref.sensors + parent_ref.actuators %}
        {% set child_class = child.ref.class|lower if child.ref.class is defined else "" %}
        {% set child_type = child.ref.__class__.__name__ %}
        {% set category =
            "sensors" if child_class == "sensor" else
            "actuators" if child_class == "actuator" else
            "actors" if child_class == "actor" else
            "obstacles" if child_class == "obstacle" else
            "composites" if child_type == "CompositeThing"
        %}
        {% set chid = child.ref.name|lower %}
        {% set dx, dy, dth = child.transformation.transformation.dx, child.transformation.transformation.dy, child.transformation.transformation.dtheta %}
        {% set abs_pose = apply_transformation(
            {'x': px, 'y': py, 'theta': pth},
            {'x': dx, 'y': dy, 'theta': dth},
            parent_shape=parent_ref.shape.__dict__ if parent_ref.shape is defined else None,
            child_shape=child.ref.shape.__dict__ if child.ref.shape is defined else None
        ) %}
        {% set chx, chy, chth = abs_pose.x, abs_pose.y, abs_pose.theta %}
        {% set chtype = child.ref.type|lower if child.ref.type else child.ref.__class__.__name__|lower %}
        {% set chsub = child.ref.subtype|lower if child.ref.subtype is defined and child.ref.subtype else None %}

        # --- child {{ chid }} ---
        {{ nodes_path }}.setdefault("{{ category }}", {}).setdefault("{{ chtype }}", {})
        {{ poses_path }}.setdefault("{{ category }}", {}).setdefault("{{ chtype }}", {})

        {% if chsub %}
        {{ nodes_path }}["{{ category }}"]["{{ chtype }}"].setdefault("{{ chsub }}", {})
        {{ poses_path }}["{{ category }}"]["{{ chtype }}"].setdefault("{{ chsub }}", {})

        {{ nodes_path }}["{{ category }}"]["{{ chtype }}"]["{{ chsub }}"]["{{ chid }}"] = {
            "class": "{{ category.rstrip('s') }}",
            "type": "{{ chtype }}",
            "subtype": "{{ chsub }}",
            "name": "{{ chid }}",
            {{ render_properties(child.ref) }}
        }
        {{ poses_path }}["{{ category }}"]["{{ chtype }}"]["{{ chsub }}"]["{{ chid }}"] = {
            "rel_pose": {"x": {{ dx }}, "y": {{ dy }}, "theta": {{ dth }}}
        }
        {% else %}
        {{ nodes_path }}["{{ category }}"]["{{ chtype }}"]["{{ chid }}"] = {
            "class": "{{ category.rstrip('s') }}",
            "type": "{{ chtype }}",
            "name": "{{ chid }}",
            {{ render_properties(child.ref) }}
        }
        {{ poses_path }}["{{ category }}"]["{{ chtype }}"]["{{ chid }}"] = {
            "rel_pose": {"x": {{ dx }}, "y": {{ dy }}, "theta": {{ dth }}}
        }
        {% endif %}

        {% if child.ref.shape is defined %}
        shape_data = {
            {{ render_shape(child.ref.shape) }}
        }
        {% if chsub %}
        {{ nodes_path }}["{{ category }}"]["{{ chtype }}"]["{{ chsub }}"]["{{ chid }}"]["shape"] = shape_data
        {{ poses_path }}["{{ category }}"]["{{ chtype }}"]["{{ chsub }}"]["{{ chid }}"]["shape"] = shape_data
        {% else %}
        {{ nodes_path }}["{{ category }}"]["{{ chtype }}"]["{{ chid }}"]["shape"] = shape_data
        {{ poses_path }}["{{ category }}"]["{{ chtype }}"]["{{ chid }}"]["shape"] = shape_data
        {% endif %}
        {% endif %}
    {% endfor %}
{% endmacro %}
{% macro register_pose_subscribers(parent_ref, parents=None) %}
    {% if parents is none %}
        {% set parents = [] %}
    {% endif %}
    
    {# === Child composites === #}
    {% for comp in parent_ref.composites %}
        {% set cname = comp.ref.name|lower %}
        {% set ctype = (comp.ref.type|lower if comp.ref.type else comp.ref.__class__.__name__|lower) %}
        {% set topic_base = topic_prefix(comp.ref, parents) | trim %}
        self.{{ cname }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_base }}.{{ cname }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ cname }}": \
                self.node_pose_callback({
                    "class": "composite",
                    "type": "{{ ctype }}",
                    "name": "{{ cname }}",
                    "x": msg.x, "y": msg.y, "theta": msg.theta
                },
                parent_pose=self.get_node_pose(
                    "{{ parents[-1][1] if parents else '' }}",
                    cls="composite",
                    type="{{ parents[-1][0] if parents else '' }}"
                ))
        )
        {{ register_pose_subscribers(comp.ref, parents + [(ctype, cname)]) }}
    {% endfor %}
    {# === Atomic children === #}
    {% for child in parent_ref.sensors + parent_ref.actuators %}
        {% set child_class = child.ref.class|lower if child.ref.class is defined else "" %}
        {% set child_type = child.ref.__class__.__name__ %}
        {% set category =
            "sensor" if child_class == "sensor" else
            "actuator" if child_class == "actuator" else
            "actor" if child_class == "actor" else
            "obstacle" if child_class == "obstacle" else
            "composites" if child_type == "CompositeThing"
        %}
        {% set chid = child.ref.name|lower %}
        {% set chtype = child.ref.type|lower if child.ref.type else child.ref.__class__.__name__|lower %}
        {% set chsub = child.ref.subtype|lower if child.ref.subtype is defined else None %}
        {% set topic_base = topic_prefix(child.ref, parents) | trim %}
        self.{{ chid }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_base }}.{{ chid }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ chid }}": \
                self.node_pose_callback({
                    "class": "{{ category.rstrip('s') }}",
                    "type": "{{ chtype }}",
                    {% if chsub %}
                    "subtype": "{{ chsub }}",
                    {% endif %}
                    "name": "{{ chid }}",
                    "x": msg.x, "y": msg.y, "theta": msg.theta
                },
                parent_pose=self.get_node_pose(
                    "{{ parents[-1][1] if parents else '' }}",
                    cls="composite",
                    type="{{ parents[-1][0] if parents else '' }}"
                ))
        )
    {% endfor %}
{% endmacro %}

class {{ environment.name }}Node(Node):
    def __init__(self, env_name: str, *args, **kwargs):
        super().__init__(
            node_name=f"{env_name.lower()}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        self.env_name = env_name
        # --- Environment dimensions ---
        self.width = {{ environment.grid[0].width }}
        self.height = {{ environment.grid[0].height }}
        self.cellSizeCm = {{ environment.grid[0].cellSizeCm }}
        self.sensor_values = {}
        self.env_properties = {
            {% for p in environment.properties %}
            "{{ p.type }}": {{ p.value }},
            {% endfor %}
        }
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
                "name": t.ref.name|lower,
                "pose": t.pose,
                "class": t.ref.class,
                "nodeclass": t.__class__.__name__,
                "category": "thing"
            }) %}
        {% endfor %}
        {% for a in environment.actors or [] %}
            {% set _ = placements.append({
                "ref": a.ref,
                "name": a.ref.name|lower,
                "pose": a.pose,
                "class": a.ref.class,
                "nodeclass": a.__class__.__name__,
                "category": "actor"
            }) %}
        {% endfor %}
        {% for o in environment.obstacles or [] %}
            {% set _ = placements.append({
                "ref": o.ref,
                "name": o.ref.name|lower,
                "pose": o.pose,
                "class": o.ref.class,
                "nodeclass": o.__class__.__name__,
                "category": "obstacle"
            }) %}
        {% endfor %}
        {% for p in placements if p.category != "obstacle" %}
            {% set name = p.name %}
            {% set ref = p.ref %}
            {% set cls = ref.class|lower %}
            {% set type = ref.type|lower if ref.type else ref.__class__.__name__|lower %}
            {% if ref.subtype %}
                {% set subtype = ref.subtype|lower %}
            {% elif nodeclass == "CompositePlacement" %}
                {# For composites, fallback to type or class name #}
                {% set subtype = ref.type|lower if ref.type else ref.__class__.__name__|lower %}
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
        {% set comp_type = type if type else (subtype if subtype else ref.__class__.__name__|lower) %}
        if "{{ comp_type }}" not in self.nodes["composites"]:
            self.nodes["composites"]["{{ comp_type }}"] = {}
            self.poses["composites"]["{{ comp_type }}"] = {}

        if "{{ name }}" not in self.nodes["composites"]["{{ comp_type }}"]:
            # Initialize node and pose dicts if not existing
            self.nodes["composites"]["{{ comp_type }}"]["{{ name }}"] = {
                "sensors": {},
                "actuators": {},
                "composites": {}
            }
            self.poses["composites"]["{{ comp_type }}"]["{{ name }}"] = {
                "x": {{ p.pose.x }},
                "y": {{ p.pose.y }},
                "theta": {{ p.pose.theta }},
                "sensors": {},
                "actuators": {},
                "composites": {}
            }
        
        # Insert composite properties into nested structure
        self.nodes["composites"]["{{ comp_type }}"]["{{ name }}"].update({
            "class": "composite",
            "type": "{{ type }}",
            "name": "{{ node_name }}",
            "pubFreq": {{ p.ref.pubFreq }},
            {{ render_properties(p.ref) }},
            "initial_pose": {
                "x": {{ p.pose.x }},
                "y": {{ p.pose.y }},
                "theta": {{ p.pose.theta }}
            }
        })

        {% if p.ref.shape is defined %}
        # --- Add top-level shape for visualizer ---
        shape_data = {
            {{ render_shape(p.ref.shape) }}
        }

        self.nodes["composites"]["{{ comp_type }}"]["{{ name }}"]["shape"] = shape_data
        self.poses["composites"]["{{ comp_type }}"]["{{ name }}"]["shape"] = shape_data

        self.poses["{{ category }}"]["{{ comp_type }}"]["{{ name }}"].update({
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        })
        {% endif %}
        {{ register_composite_children(
            "self.nodes['composites']['" ~ comp_type ~ "']['" ~ name ~ "']",
            "self.poses['composites']['" ~ comp_type  ~ "']['" ~ name ~ "']",
            p.ref,
            {'x': p.pose.x, 'y': p.pose.y, 'theta': p.pose.theta},
            name
        ) }}
        {% else %}
        {# --- Initialization of sensors, actuators, actors --- #}
        # Ensure category exists
        if "{{ category }}" not in self.nodes:
            self.nodes["{{ category }}"] = {}
            self.poses["{{ category }}"] = {}

        # --- Hierarchical structure setup ---
        {% if type and subtype and subtype != type %}
        # Case 1: category[type][subtype][name]
        if "{{ type }}" not in self.nodes["{{ category }}"]:
            self.nodes["{{ category }}"]["{{ type }}"] = {}
            self.poses["{{ category }}"]["{{ type }}"] = {}

        if "{{ subtype }}" not in self.nodes["{{ category }}"]["{{ type }}"]:
            self.nodes["{{ category }}"]["{{ type }}"]["{{ subtype }}"] = {}
            self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"] = {}

        self.nodes["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ name }}"] = {}
        self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ name }}"] = {}

        self.nodes["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ name }}"] = {
            "class": "{{ cls }}",
            "type": "{{ type }}",
            "subtype": "{{ subtype }}",
            "name": "{{ node_name }}",
            "pubFreq": {{ p.ref.pubFreq }},
            {{ render_properties(p.ref) }}
        }

        # --- Add shape if exists ---
        {% if p.ref.shape is defined %}
        shape_data = {
            {{ render_shape(p.ref.shape) }}
        }
        self.nodes["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ name }}"]["shape"] = shape_data
        self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ name }}"]["shape"] = shape_data
        {% endif %}
        {% if node_name == "linearalarm" %}
        self.poses["{{ category }}"]["{{ type  }}"]["{{ subtype }}"]["{{ name }}"] = {
            "start": {
                "x": {{ p.ref.shape.points[0].x }},
                "y": {{ p.ref.shape.points[0].y }}
            },
            "end": {
                "x": {{ p.ref.shape.points[1].x }},
                "y": {{ p.ref.shape.points[1].y }}
            }
        }
        {% endif %}
        
        self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ name }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        {% elif type %}
        # Case 2: category[type][name]
        if "{{ type }}" not in self.nodes["{{ category }}"]:
            self.nodes["{{ category }}"]["{{ type }}"] = {}
            self.poses["{{ category }}"]["{{ type }}"] = {}

        self.nodes["{{ category }}"]["{{ type }}"]["{{ name }}"] = {}
        self.poses["{{ category }}"]["{{ type }}"]["{{ name }}"] = {}

        # Case: {{ category }}["{{ type }}"]["{{ name }}"]
        self.nodes["{{ category }}"]["{{ type }}"]["{{ name }}"] = {
            "class": "{{ cls }}",
            "type": "{{ type }}",
            "name": "{{ node_name }}",
            "pubFreq": {{ p.ref.pubFreq }},
            {{ render_properties(p.ref) }}
        }

        # --- Add shape if exists ---
        {% if p.ref.shape is defined %}
        shape_data = {
            {{ render_shape(p.ref.shape) }}
        }

        self.nodes["{{ category }}"]["{{ type }}"]["{{ name }}"]["shape"] = shape_data
        self.poses["{{ category }}"]["{{ type }}"]["{{ name }}"]["shape"] = shape_data
        
        self.poses["{{ category }}"]["{{ type }}"]["{{ name }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        
        {% endif %}
        {% endif %}
        {% endif %}
        self.tree[self.env_name.lower()].append("{{ name }}")

        {% if p.nodeclass == "CompositePlacement" %}
        {% set comp_type = type if type else (subtype if subtype else ref.__class__.__name__|lower) %}
        
        {{ register_pose_subscribers(p.ref, [(type, name)]) }}
        {% endif %}

        # Define {{ name }} subscriber
        {% set parent_tuple = (p.ref.parent.subtype, p.ref.parent.name) if p.ref.parent is defined else None %}
        {% set topic_base = topic_prefix(p.ref, parent_tuple) | trim %}
        self.{{ name }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_base }}.{{ name }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ name }}": \
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
                }{% if p.nodeclass == "CompositePlacement" %}, parent_pose=None  # top-level composite in environment
                {% elif ref.class|lower in ["sensor", "actuator", "actor"] %}, parent_pose=None  # top-level thing in environment
                {% elif ref.class|lower == "composite" %}
                    {% set parent_tuple = (p.ref.parent.subtype, p.ref.parent.name) if p.ref.parent is defined else None %}
                    {% if parent_tuple %}, parent_pose=self.get_node_pose(
                        "{{ parent_tuple[1]|lower }}",
                        cls="composite",
                        type="{{ parent_tuple[0]|lower if parent_tuple[0] else '' }}"
                    )
                    {% else %}
                    , parent_pose=None
                    {% endif %}
                {% endif %})
        )

        {% if cls == "sensor" %}
        {% set subtype_orig = ref.subtype if ref.subtype is defined and ref.subtype else None %}
        {% set type_orig = ref.type if ref.type else ref.__class__.__name__ %}
        {% set node_classname = camelcase(subtype_orig) if subtype_orig else camelcase(type_orig) %}
        # Data subscriber
        self.{{ name }}_data_sub = self.create_subscriber(
            topic=f"sensor.{{ type }}{{ '.' ~ subtype if subtype and subtype != type else '' }}.{{ name }}.data",
            msg_type={{ node_classname }}Message,
            on_message=lambda msg, chid="{{ name }}": self._on_sensor_data(msg, chid)
        )
        {% endif %}
        {% endfor %}
        
        # Obstacles (static, non-node entities)
        self.nodes["obstacles"] = {}
        self.poses["obstacles"] = {}
        {% for p in placements if p.category == "obstacle" %}
        {% set name = p.name %}
        {% set ref = p.ref %}
        {% set shape = ref.shape if ref.shape is defined else None %}
        # Define obstacle {{ name }}
        self.nodes["obstacles"]["{{ name }}"] = {
            "class": "obstacle",
            "name": "{{ name }}",
            "shape": {
                "type": "{{ shape.__class__.__name__ if shape else 'Square' }}",
                {% if shape and shape.__class__.__name__ == "Rectangle" %}
                "width": {{ shape.width }},
                "length": {{ shape.length }}
                {% elif shape and shape.__class__.__name__ == "Square" %}
                "length": {{ shape.length }}
                {% elif shape and shape.__class__.__name__ == "Circle" %}
                "radius": {{ shape.radius }}
                {% else %}
                "length": 10.0
                {% endif %}
            }
        }
        self.poses["obstacles"]["{{ name }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }},
            "shape": self.nodes["obstacles"]["{{ name }}"]["shape"]
        }
        {% endfor %}

    # Wrappers for affection and pose utils
    def check_affectability(self, sensor_id: str, env_properties, env=None):
        return check_affectability(self.nodes, self.poses, self.log, sensor_id, env_properties, env)

    def node_pose_callback(self, node: dict, parent_pose):
        return node_pose_callback(self.nodes, self.poses, self.log, node, parent_pose)

    def get_node_pose(self, name, cls, type=None, subtype=None):
        """
        Retrieve the current pose of a node (sensor, actuator, composite, etc.)
        from self.poses hierarchy.
        Returns None if not found.
        """
        category = f"{cls}s"  # e.g., sensors, actuators, composites
        try:
            if subtype:
                return self.poses[category][type][subtype][name]
            else:
                return self.poses[category][type][name]
        except KeyError:
            return None

    def _on_sensor_data(self, msg, sensor_id):
        """Receive live sensor data from child nodes."""
        if not hasattr(self, "sensor_values"):
            self.sensor_values = {}
        try:
            # Try to extract the first numeric field (temperature, humidity, etc.)
            data_dict = msg.__dict__
            val = None
            for k, v in data_dict.items():
                if isinstance(v, (int, float)) and k not in ("range", "pubFreq"):
                    val = v
                    break
            if val is not None:
                self.sensor_values[sensor_id] = val
                self.log.debug(f"[SensorData] {sensor_id} = {val}")
        except Exception as e:
            self.log.error(f"[SensorData] Error for {sensor_id}: {e}")

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
                elif "rel_pose" in p and all(k in p["rel_pose"] for k in ["x", "y", "theta"]):
                    r = p["rel_pose"]
                    return f"(rel_pose=({r['x']:.2f},{r['y']:.2f},{r['theta']:.2f} deg))"
            return ""

        def is_pose(p):
            """Check if dict is a pose."""
            return isinstance(p, dict) and (
                all(k in p for k in ["x", "y", "theta"]) or
                ("rel_pose" in p and all(k in p["rel_pose"] for k in ["x", "y", "theta"])) or
                ("start" in p and "end" in p)
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
                            for name, val in group.items():
                                if is_pose(val):
                                    self.log.info(f"{pad}        - {name} {format_pose(val)}")
                                    recurse(name, val, indent + 3)
                                elif isinstance(val, dict):
                                    recurse(name, val, indent + 2)
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

    def update_affections(self):
        """Continuously evaluate affectability for all passive sensors (exclude RPC-based ones)."""
        self.log.info("[Env] Affections update thread started.")

        # --- List of active sensors handled via RPC ---
        active_rpc_sensors = {"camera", "rfid", "microphone"}

        def recurse_children(node_dict):
            """Recursively walk through composites and evaluate sensor affections."""
            if not isinstance(node_dict, dict):
                return

            for node_id, node in node_dict.items():
                node_class = getattr(node, "node_class", None)
                node_type = getattr(node, "type", "").lower()
                node_subtype = getattr(node, "subtype", "").lower()

                # --- Skip active RPC-based sensors (camera, rfid, microphone) ---
                if node_class == "sensor" and (
                    node_type in active_rpc_sensors or node_subtype in active_rpc_sensors
                ):
                    self.log.info(f"[Affection] Skipping RPC-based sensor {node_id} ({node_type}/{node_subtype})")
                    continue

                # --- Only evaluate passive sensors automatically ---
                if node_class == "sensor":
                    aff_handler = getattr(node, "affection_handler", None)
                    if callable(aff_handler):
                        try:
                            result = aff_handler(node_id, self.env_properties)
                            node._sim_data = result
                            self.log.info(f"[Affection] {node_id} -> {node._sim_data}")
                            # Store for visualizer
                            if isinstance(result, dict):
                                if "affections" in result:
                                    self.sensor_values[node_id] = result["affections"]
                                else:
                                    self.sensor_values[node_id] = result
                        except Exception as e:
                            self.log.error(f"[AffectionError] {node_id}: {e}")

                # --- If node has children (e.g., composite), recurse deeper ---
                if hasattr(node, "children") and isinstance(node.children, dict):
                    recurse_children(node.children)

        while getattr(self, "running", False):
            try:
                recurse_children(getattr(self, "children", {}))
            except Exception as e:
                self.log.error(f"[update_affections] {e}")
            time.sleep(1.0)

    def start(self):
        """Start environment and all top-level components."""
        if getattr(self, "running", False):
            return
        print(f"[{{ environment.name }}Node] Starting environment...")
        self.running = True
        # === Debug: print environment hierarchy ===
        # import json
        # print("\n=== ENV STRUCTURE: NODES ===")
        # print(json.dumps(self.nodes, indent=2))
        # print("\n=== ENV STRUCTURE: POSES ===")
        # print(json.dumps(self.poses, indent=2))
        self.print_tf_tree()

        # Start commlib internal loop
        self._thread = threading.Thread(target=self.run)
        self._thread.start()
        time.sleep(0.5)

        # Start top-level child nodes (sensors, actuators, composites)
        self.children = {}
        {% set placements = (environment.things or []) + (environment.composites or []) %}
        {% for p in placements %}
            {% set ref = p.ref %}
            {% set cls = ref.class|lower %}
            {% set type_orig = ref.type if ref.type else ref.__class__.__name__ %}
            {% set subtype_orig = ref.subtype if ref.subtype is defined and ref.subtype else None %}
            {% set node_classname = camelcase(subtype_orig) if subtype_orig else camelcase(type_orig) %}
            {% set name = ref.name|lower %}
            {% set node_class = 
                ("composite" if cls == "composite" or p.__class__.__name__ == "CompositePlacement"
                else "sensor" if cls == "sensor"
                else "actuator" if cls == "actuator"
                else "actor") %}
            {% set pose = p.pose %}
        try:
            print(f"[{{ environment.name }}Node] Starting {{ node_class }} '{{ name }}' {{ node_classname }}Node)")
            kwargs = {}
            {% if node_class  == "sensor" %}
            kwargs["sensor_id"] = "{{ name }}"
            {% elif node_class  == "actuator" %}
            kwargs["actuator_id"] = "{{ name }}"
            {% elif node_class  == "composite" %}
            kwargs["composite_id"] = "{{ name }}"
            {% elif node_class  == "actor" %}
            kwargs["actor_id"] = "{{ name }}"
            {% endif %}

            node = {{ node_classname }}Node(
                parent_topic="",
                initial_pose={'x': {{ pose.x }}, 'y': {{ pose.y }}, 'theta': {{ pose.theta }}},
                affection_handler=getattr(self, "check_affectability", None),
                **kwargs
            )
            node.start()
            self.children["{{ name }}"] = node
        except Exception as e:
            print(f"[{{ environment.name }}Node] ERROR launching '{{ name }}': {e}")
        
        {% endfor %}

        # === RPC services for active sensors (camera, rfid, microphone) ===
        rpc_sensors = {"camera", "rfid", "microphone"}
        print(f"[DEBUG] Starting RPC registration in {self.env_name}...")
        # import json
        # print("[DEBUG] Dumping node keys before RPC registration:")
        # print(json.dumps(self.nodes, indent=2)[:20000])  # limit to avoid spam
        def _register_rpc_recursively(tree, path="root"):
            if not isinstance(tree, dict):
                return

            # ---- Case: this dict itself represents a node ----
            if "class" in tree:
                node_type = str(tree.get("type", "")).lower()
                node_sub = str(tree.get("subtype", "")).lower()
                name = tree.get("name", "")
                full_path = f"{path}/{name}"

                if node_sub in rpc_sensors or node_type in rpc_sensors:
                    # Convert the recursive path to a commlib-style RPC name
                    clean_path = path.replace("root/", "").replace("/", ".")
                    # Convert plural to singular to match node topic conventions
                    clean_path = (
                        clean_path
                        .replace("composites.", "composite.")
                        .replace("sensors.", "sensor.")
                        .replace("actuators.", "actuator.")
                        .replace("actors.", "actor.")
                        .replace("obstacles.", "obstacle.")
                    )
                    # Avoid duplicating the final node name if it's already in the path
                    if clean_path.endswith(f".{name}"):
                        rpc_name = f"{clean_path}.read"
                    else:
                        rpc_name = f"{clean_path}.{name}.read"

                    print("=" * 60)
                    print(f"[RPC_REGISTER] class={tree['class']} type={node_type} subtype={node_sub}")
                    print(f"[RPC_REGISTER] name={name}")
                    print(f"[RPC_REGISTER] FULL PATH: {full_path}")
                    print(f"[RPC_REGISTER] REGISTERING RPC: {rpc_name}")
                    print("=" * 60)
                    try:
                        rpc_srv = self.create_rpc(rpc_name=rpc_name, on_request=self._on_rpc_read)
                        setattr(self, f"rpc_{name}_read", rpc_srv)
                        self.log.info(f"[RPC] Registered RPC for {name} at '{rpc_name}'")
                    except Exception as e:
                        self.log.error(f"[RPC] Failed for {name} ({rpc_name}): {e}")

            # ---- Always recurse into sub-dicts ----
            for key, child in tree.items():
                if isinstance(child, dict):
                    _register_rpc_recursively(child, path=f"{path}/{key}")

        _register_rpc_recursively(self.nodes)
        print("[DEBUG] Active RPC attributes in HomeNode:")
        for k, v in self.__dict__.items():
            if k.startswith("rpc_") and "_read" in k:
                print(f"   - {k}: {v}")

        
        # Start affection updater thread
        self._aff_thread = threading.Thread(target=self.update_affections, daemon=True)
        self._aff_thread.start()

        # Environment main loop
        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("[{{ environment.name }}Node] Interrupted.")
            self.stop()

    def _on_rpc_read(self, msg):
        """
        Shared RPC handler for active sensors (camera, rfid, microphone).
        Simply delegates to the environment's affection system.
        """
        self.log.info(f"[RPCRead] Request received: {msg}")
        sensor_id = msg.get("sensor_id")
        if not sensor_id:
            return {"error": "Missing 'sensor_id'"}
        try:
            result = self.check_affectability(sensor_id, self.env_properties, self)
            # Normalize result
            if isinstance(result, dict):
                return result
            return {"result": result}
        except Exception as e:
            self.log.error(f"[RPCRead] {sensor_id}: {e}")
            return {"error": str(e)}

    def stop(self):
        """Stop environment and all children cleanly."""
        print(f"[{self.__class__.__name__}] Stopping environment...")
        self.running = False

        if hasattr(self, "children"):
            for name, child in self.children.items():
                try:
                    print(f"  -> stopping child {name}")
                    child.stop()
                except Exception as e:
                    print(f"  [WARN] Could not stop {name}: {e}")

        if hasattr(self, "_aff_thread") and self._aff_thread.is_alive():
            self._aff_thread.join(timeout=1.0)

        if hasattr(self, "_thread") and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        try:
            super().stop()
        except Exception:
            pass
        print(f"[{self.__class__.__name__}] Stopped.")

if __name__ == '__main__':
    import threading

    # --- Ensure Redis is running ---
    try:
        redis.Redis(host='localhost', port=6379).ping()
        print("[Redis] Connected successfully.")
    except redis.exceptions.ConnectionError:
        print("[Redis] Not running. Start Redis server first.")
        sys.exit(1)

    node = HomeNode(env_name="Home")

    # Start the environment node in its own thread
    env_thread = threading.Thread(target=node.start, daemon=True)
    env_thread.start()
    time.sleep(1.0)

    # Start visualizer in the MAIN thread (no lag, proper event loop)
    vis = EnvVisualizer(node)

    try:
        vis.render()  # blocking call, runs at ~30 FPS internally
    except KeyboardInterrupt:
        print("\n[System] Interrupted by user.")
    finally:
        print("[System] Shutting down cleanly...")
        vis.stop()
        node.stop()
        if env_thread.is_alive():
            env_thread.join(timeout=2.0)
        sys.exit(0)