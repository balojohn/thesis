import sys, time, threading, logging, redis, math
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from omnisim.utils.visualizer import EnvVisualizer
from omnisim.utils.geometry import node_pose_callback
# Affection handlers
from omnisim.utils.affections import check_affectability
# Generated node classes
{% set placements = (environment.things or []) + (environment.composites or []) %}
{% for p in placements %}
    {% set ref = p.ref %}
    {% set cls = ref.class|lower %}
    {% set type = ref.type|lower if ref.type else ref.__class__.__name__|lower %}
    {% set subtype = ref.subtype|lower if ref.subtype is defined and ref.subtype else None %}
    {% set node_classname = subtype|capitalize if subtype else type|capitalize %}
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
    {% else %}
        {% set _ = parts.append("composite." ~ type_part) %}
    {% endif %}

    {{ parts | join('.') }}
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
        {% if comp.ref.shape is defined and comp.ref.shape %}
        {{ poses_path }}["composites"]["{{ ctype }}"]["{{ cid }}"]["shape"] = {
            "type": "{{ comp.ref.shape.__class__.__name__ }}",
            {% if comp.ref.shape.__class__.__name__ == "Rectangle" %}
            "width": {{ comp.ref.shape.width }},
            "length": {{ comp.ref.shape.length }}
            {% elif comp.ref.shape.__class__.__name__ == "Square" %}
            "size": {{ comp.ref.shape.length }}
            {% elif comp.ref.shape.__class__.__name__ == "Circle" %}
            "radius": {{ comp.ref.shape.radius }}
            {% elif comp.ref.shape.__class__.__name__ in ["Line","ArbitraryShape"] %}
            "points": [
                {% for pt in comp.ref.shape.points %}
                {"x": {{ pt.x }}, "y": {{ pt.y }}},
                {% endfor %}
            ]
            {% endif %}
        }
        {{ nodes_path }}["composites"]["{{ ctype }}"]["{{ cid }}"]["shape"] = {{ poses_path }}["composites"]["{{ ctype }}"]["{{ cid }}"]["shape"]
        {% endif %}
        {{ register_composite_children(
            nodes_path ~ "['composites']['" ~ ctype ~ "']['" ~ cid ~ "']",
            poses_path ~ "['composites']['" ~ ctype ~ "']['" ~ cid ~ "']",
            comp.ref,
            {'x': cx, 'y': cy, 'theta': cth},
            cid
        ) }}
    {% endfor %}
    {# === Child sensors === #}
    {% for sen in parent_ref.sensors %}
        {% set sid = sen.ref.name|lower %}
        {% set dx, dy, dth = sen.transformation.transformation.dx, sen.transformation.transformation.dy, sen.transformation.transformation.dtheta %}
        {% set abs_pose = apply_transformation(
            {'x': px, 'y': py, 'theta': pth},
            {'x': dx, 'y': dy, 'theta': dth},
            parent_shape=parent_ref.shape.__dict__ if parent_ref.shape is defined else None,
            child_shape=sen.ref.shape.__dict__ if sen.ref.shape is defined else None
        ) %}
        {% set sx, sy, sth = abs_pose.x, abs_pose.y, abs_pose.theta %}
        {% set stype = sen.ref.type|lower if sen.ref.type else sen.ref.__class__.__name__|lower %}
        {% set ssub = sen.ref.subtype|lower if sen.ref.subtype is defined and sen.ref.subtype else None %}
        # --- sensor {{ sid }} ---
        {{ poses_path }}["sensors"]["{{ sid }}"] = {
            "rel_pose": {"x": {{ dx }}, "y": {{ dy }}, "theta": {{ dth }}},
        }
        {% if sen.ref.shape is defined and sen.ref.shape %}
        {{ poses_path }}["sensors"]["{{ sid }}"]["shape"] = {
            "type": "{{ sen.ref.shape.__class__.__name__ }}",
            {% if sen.ref.shape.__class__.__name__ == "Rectangle" %}
            "width": {{ sen.ref.shape.width }},
            "length": {{ sen.ref.shape.length }}
            {% elif sen.ref.shape.__class__.__name__ == "Square" %}
            "size": {{ sen.ref.shape.length }}
            {% elif sen.ref.shape.__class__.__name__ == "Circle" %}
            "radius": {{ sen.ref.shape.radius }}
            {% endif %}
        }
        {% endif %}
        {{ nodes_path }}["sensors"]["{{ sid }}"] = {
            "class": "sensor",
            "type": "{{ stype }}",
            {% if ssub %}
            "subtype": "{{ ssub }}",
            {% endif %}
            "name": "{{ sid }}",
            {% if sen.ref.shape is defined and sen.ref.shape %}
            "shape": {
                "type": "{{ sen.ref.shape.__class__.__name__ }}",
                {% if sen.ref.shape.__class__.__name__ == "Rectangle" %}
                "width": {{ sen.ref.shape.width }},
                "length": {{ sen.ref.shape.length }}
                {% elif sen.ref.shape.__class__.__name__ == "Square" %}
                "size": {{ sen.ref.shape.length }}
                {% elif sen.ref.shape.__class__.__name__ == "Circle" %}
                "radius": {{ sen.ref.shape.radius }}
                {% endif %}
            }
            {% endif %}
        }
    {% endfor %}
    {# === Child actuators === #}
    {% for act in parent_ref.actuators %}
        {% set aid = act.ref.name|lower %}
        {% set dx, dy, dth = act.transformation.transformation.dx, act.transformation.transformation.dy, act.transformation.transformation.dtheta %}
        {% set abs_pose = apply_transformation(
            {'x': px, 'y': py, 'theta': pth},
            {'x': dx, 'y': dy, 'theta': dth},
            parent_shape=parent_ref.shape.__dict__ if parent_ref.shape is defined else None,
            child_shape=act.ref.shape.__dict__ if act.ref.shape is defined else None
        ) %}
        {% set ax, ay, ath = abs_pose.x, abs_pose.y, abs_pose.theta %}
        {% set atype = act.ref.type|lower if act.ref.type else act.ref.__class__.__name__|lower %}
        {% set asub = act.ref.subtype|lower if act.ref.subtype is defined and act.ref.subtype else None %}
        # --- actuator {{ aid }} ---
        {{ poses_path }}["actuators"]["{{ aid }}"] = {
            "rel_pose": {"x": {{ dx }}, "y": {{ dy }}, "theta": {{ dth }}},
        }
        {% if act.ref.shape is defined and act.ref.shape %}
        {{ poses_path }}["actuators"]["{{ aid }}"]["shape"] = {
            "type": "{{ act.ref.shape.__class__.__name__ }}",
            {% if act.ref.shape.__class__.__name__ == "Rectangle" %}
            "width": {{ act.ref.shape.width }},
            "length": {{ act.ref.shape.length }}
            {% elif act.ref.shape.__class__.__name__ == "Square" %}
            "size": {{ act.ref.shape.length }}
            {% elif act.ref.shape.__class__.__name__ == "Circle" %}
            "radius": {{ act.ref.shape.radius }}
            {% endif %}
        }
        {% endif %}
        {{ nodes_path }}["actuators"]["{{ aid }}"] = {
            "class": "actuator",
            "type": "{{ atype }}",
            {% if asub %}
            "subtype":"{{ asub }}",
            {% endif %}
            "name": "{{ aid }}",
            {% if act.ref.shape is defined and act.ref.shape %}
            "shape": {
                "type": "{{ act.ref.shape.__class__.__name__ }}",
                {% if act.ref.shape.__class__.__name__ == "Rectangle" %}
                "width": {{ act.ref.shape.width }},
                "length": {{ act.ref.shape.length }}
                {% elif act.ref.shape.__class__.__name__ == "Square" %}
                "size": {{ act.ref.shape.length }}
                {% elif act.ref.shape.__class__.__name__ == "Circle" %}
                "radius": {{ act.ref.shape.radius }}
                {% endif %}
            }
            {% endif %}
        }
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
    {# === Child sensors === #}
    {% for sen in parent_ref.sensors %}
        {% set sid = sen.ref.name|lower %}
        {% set stype = sen.ref.type|lower if sen.ref.type else sen.ref.__class__.__name__|lower %}
        {% set ssub = sen.ref.subtype|lower if sen.ref.subtype is defined and sen.ref.subtype else None %}
        {% set topic_base = topic_prefix(sen.ref, parents) | trim %}
        self.{{ sid }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_base }}.{{ sid }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ sid }}": \
                self.node_pose_callback({
                    "class": "sensor",
                    "type": "{{ stype }}",
                    {% if ssub %}
                    "subtype": "{{ ssub }}",
                    {% endif %}
                    "name": "{{ sid }}",
                    "x": msg.x, "y": msg.y, "theta": msg.theta
                },
                parent_pose=self.get_node_pose(
                    "{{ parents[-1][1] if parents else '' }}",
                    cls="composite",
                    type="{{ parents[-1][0] if parents else '' }}"
                ))
        )
    {% endfor %}
    {# === Child actuators === #}
    {% for act in parent_ref.actuators %}
        {% set aid = act.ref.name|lower %}
        {% set atype = act.ref.type|lower if act.ref.type else act.ref.__class__.__name__|lower %}
        {% set asub = act.ref.subtype|lower if act.ref.subtype is defined and act.ref.subtype else None %}
        {% set topic_base = topic_prefix(act.ref, parents) | trim %}
        self.{{ aid }}_pose_sub = self.create_subscriber(
            topic=f"{{ topic_base }}.{{ aid }}.pose",
            msg_type=PoseMessage,
            on_message=lambda msg, name="{{ aid }}": \
                self.node_pose_callback({
                    "class": "actuator",
                    "type": "{{ atype }}",
                    {% if asub %}
                    "subtype": "{{ asub }}",
                    {% endif %}
                    "name": "{{ aid }}",
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
            },
            "initial_pose": {
                "x": {{ p.pose.x }},
                "y": {{ p.pose.y }},
                "theta": {{ p.pose.theta }}
            }
        })
        {% if p.ref.shape is defined and p.ref.shape %}
        # --- Add top-level shape for visualizer ---
        shape_data = {
            "type": "{{ p.ref.shape.__class__.__name__ }}",
            {% if p.ref.shape.__class__.__name__ == "Rectangle" %}
            "width": {{ p.ref.shape.width }},
            "length": {{ p.ref.shape.length }}
            {% elif p.ref.shape.__class__.__name__ == "Square" %}
            "length": {{ p.ref.shape.length }}
            {% elif p.ref.shape.__class__.__name__ == "Circle" %}
            "radius": {{ p.ref.shape.radius }}
            {% elif p.ref.shape.__class__.__name__ == "Line" %}
            "points": [
                {"x": {{ p.ref.shape.points[0].x }}, "y": {{ p.ref.shape.points[0].y }}},
                {"x": {{ p.ref.shape.points[1].x }}, "y": {{ p.ref.shape.points[1].y }}}
            ]
            {% elif p.ref.shape.__class__.__name__ == "ArbitraryShape" %}
            "points": [
                {% for pt in p.ref.shape.points %}
                {"x": {{ pt.x }}, "y": {{ pt.y }}},
                {% endfor %}
            ]
            {% endif %}
        }
        self.nodes["composites"]["{{ comp_key }}"]["{{ inst }}"]["shape"] = shape_data
        self.poses["composites"]["{{ comp_key }}"]["{{ inst }}"]["shape"] = shape_data
        {% endif %}
        {% else %}
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
            },
        }
        # --- Add top-level shape for visualizer ---
        {% if p.ref.shape is defined and p.ref.shape %}
        shape_data = {
            "type": "{{ p.ref.shape.__class__.__name__ }}",
            {% if p.ref.shape.__class__.__name__ == "Rectangle" %}
            "width": {{ p.ref.shape.width }},
            "length": {{ p.ref.shape.length }}
            {% elif p.ref.shape.__class__.__name__ == "Square" %}
            "size": {{ p.ref.shape.length }}
            {% elif p.ref.shape.__class__.__name__ == "Circle" %}
            "radius": {{ p.ref.shape.radius }}
            {% elif p.ref.shape.__class__.__name__ == "Line" %}
            "points": [
                {"x": {{ p.ref.shape.points[0].x }}, "y": {{ p.ref.shape.points[0].y }}},
                {"x": {{ p.ref.shape.points[1].x }}, "y": {{ p.ref.shape.points[1].y }}}
            ]
            {% elif p.ref.shape.__class__.__name__ == "ArbitraryShape" %}
            "points": [
                {% for pt in p.ref.shape.points %}
                {"x": {{ pt.x }}, "y": {{ pt.y }}},
                {% endfor %}
            ]
            {% endif %}
        }
        {% else %}
        # Default shape if none specified
        shape_data = {
            "type": "Circle",
            "radius": 3.0
        }
        {% endif %}
        self.nodes["{{ inst }}"]["shape"] = shape_data
        {% endif %}

        # Define {{ inst }} pose
        {% if category == "composites" %}
        {% set comp_key = type if type else (subtype if subtype else ref.__class__.__name__|lower) %}
        self.poses["{{ category }}"]["{{ comp_key }}"]["{{ inst }}"].update({
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        })
        self.poses["{{ category }}"]["{{ comp_key }}"]["{{ inst }}"]["shape"] = shape_data
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
        self.poses["{{ category }}"]["{{ type  }}"]["{{ subtype }}"]["{{ inst }}"]["shape"] = shape_data
            {% elif type and subtype %}
        self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        self.poses["{{ category }}"]["{{ type }}"]["{{ subtype }}"]["{{ inst }}"]["shape"] = shape_data
            {% elif type %}
        self.poses["{{ category }}"]["{{ type }}"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        self.poses["{{ category }}"]["{{ type }}"]["{{ inst }}"]["shape"] = shape_data
            {% else %}
        self.poses["{{ category }}"]["{{ node_name }}"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }}
        }
        self.poses["{{ category }}"]["{{ node_name }}"]["{{ inst }}"]["shape"] = shape_data
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
        {{ register_pose_subscribers(p.ref, [(type, inst)]) }}
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
        # Data subscriber
        self.{{ inst }}_data_sub = self.create_subscriber(
            topic=f"sensor.{{ type }}.{{ subtype if subtype else type }}.{{ inst }}.data",
            msg_type={{ subtype|capitalize if subtype else type|capitalize }}Message,
            on_message=lambda msg, sid="{{ inst }}": self._on_sensor_data(msg, sid)
        )
        {% endif %}

        {% endfor %}
        # Obstacles (static, non-node entities)
        self.nodes["obstacles"] = {}
        self.poses["obstacles"] = {}
        {% for p in placements if p.category == "obstacle" %}
        {% set inst = p.inst %}
        {% set ref = p.ref %}
        {% set shape = ref.shape if ref.shape is defined else None %}
        # Define obstacle {{ inst }}
        self.nodes["obstacles"]["{{ inst }}"] = {
            "class": "obstacle",
            "name": "{{ inst }}",
            "shape": {
                "type": "{{ shape.__class__.__name__ if shape else 'Square' }}",
                {% if shape and shape.__class__.__name__ == "Rectangle" %}
                "width": {{ shape.width }},
                "length": {{ shape.length }}
                {% elif shape and shape.__class__.__name__ == "Square" %}
                "size": {{ shape.length }}
                {% elif shape and shape.__class__.__name__ == "Circle" %}
                "radius": {{ shape.radius }}
                {% else %}
                "size": 10.0
                {% endif %}
            }
        }
        self.poses["obstacles"]["{{ inst }}"] = {
            "x": {{ p.pose.x }},
            "y": {{ p.pose.y }},
            "theta": {{ p.pose.theta }},
            "shape": self.nodes["obstacles"]["{{ inst }}"]["shape"]
        }
        {% endfor %}

    # Wrappers for affection and pose utils
    def check_affectability(self, sensor_id: str, env_properties, lin_alarms_robots=None):
        return check_affectability(self.nodes, self.poses, self.log, sensor_id, env_properties, lin_alarms_robots)

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

    def update_affections(self):
        """Continuously evaluate affectability for all child nodes."""
        self.log.info("[Env] Affections update thread started.")
        while getattr(self, "running", False):
            try:
                for node_id, node in getattr(self, "children", {}).items():
                    # Only consider sensors for affectability
                    node_class = getattr(node, "node_class", None)
                    if node_class != "sensor":
                        continue
                    aff_handler = getattr(node, "affection_handler", None)
                    if not callable(aff_handler):
                        continue

                    # Compute and store the simulated data
                    result = aff_handler(node_id, self.env_properties)
                    node._sim_data = result
                    self.log.info(f"[Affection] {node_id} -> {node._sim_data}")
            except Exception as e:
                self.log.error(f"[update_affections] {e}")

            # Control update frequency
            time.sleep(1.0)

    def start(self):
        """Start environment and all top-level components."""
        if getattr(self, "running", False):
            return
        print(f"[{{ environment.name }}Node] Starting environment...")
        self.running = True
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
            {% set type = ref.type|lower if ref.type else ref.__class__.__name__|lower %}
            {% set subtype = ref.subtype|lower if ref.subtype is defined and ref.subtype else None %}
            {% set inst = p.instance_id if p.instance_id else ref.name|lower %}
            {% set node_classname = subtype|capitalize if subtype else type|capitalize %}
            {% set node_class = 
                ("composite" if cls == "composite" or p.__class__.__name__ == "CompositePlacement"
                else "sensor" if cls == "sensor"
                else "actuator" if cls == "actuator"
                else "actor") %}
            {% set pose = p.pose %}
        try:
            print(f"[{{ environment.name }}Node] Starting {{ node_class }} '{{ inst }}' {{ node_classname }}Node)")
            kwargs = {}
            {% if node_class  == "sensor" %}
            kwargs["sensor_id"] = "{{ inst }}"
            {% elif node_class  == "actuator" %}
            kwargs["actuator_id"] = "{{ inst }}"
            {% elif node_class  == "composite" %}
            kwargs["composite_id"] = "{{ inst }}"
            {% elif node_class  == "actor" %}
            kwargs["actor_id"] = "{{ inst }}"
            {% endif %}

            node = {{ node_classname }}Node(
                parent_topic="",
                initial_pose={'x': {{ pose.x }}, 'y': {{ pose.y }}, 'theta': {{ pose.theta }}},
                affection_handler=getattr(self, "check_affectability", None),
                **kwargs
            )
            node.start()
            self.children["{{ inst }}"] = node
        except Exception as e:
            print(f"[{{ environment.name }}Node] ERROR launching '{{ inst }}': {e}")
        
        {% endfor %}

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
