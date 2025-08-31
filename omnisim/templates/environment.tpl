import sys, time, threading, subprocess, redis
from typing import Dict, Tuple, Any
from commlib.msg import PubSubMessage
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

class EnvironmentNode(Node):
    def __init__(self, env_name: str = "environment", *args, **kwargs):
        super().__init__(
            node_name=f"{env_name.lower()}",
            connection_params=ConnectionParameters(),
            *args, **kwargs
        )
        self.poses: Dict[Tuple[str,str], dict] = {}
        self.data: Dict[Tuple[str,str], Any] = {}
        self._subs = []
        {% for p in placements %}
            {%- set ref = p.ref %}
            {%- set subclass = ref.__class__.__name__ | lower -%}
            {% set type_seg = ('.' ~ (ref.type | lower)) if (ref.type is defined and ref.type) else '' %}
            {% set base_default = subclass ~ type_seg %}
            {% set base = p.poseTopic if p.poseTopic else base_default %}
            {% set inst_id = (ref.name | lower) ~ '_1' %}
            {% set msg_types = [] %}
            {%- for comm in comms.communications -%}
              {%- for e in comm.endpoints -%}
                {% if e.__class__.__name__ == "Publisher" and e.topic.startswith(base) and e.msg is not none %}
                  {% set _ = msg_types.append(e.msg.name) %} 
                {%- endif -%}
              {%- endfor -%}
            {%- endfor %}

        # ---- {{ ref.name }} subscriber ----
        self._subs.append(self.create_subscriber(
            topic=f"{{ base }}.{{ inst_id }}.pose",
            msg_type=PoseMessage,
            on_message=self._{{ inst_id }}_pose
        ))

        self._subs.append(self.create_subscriber(
            topic=f"{{ base }}.{{ inst_id }}",
            msg_type={{ msg_types[-1] }},
            on_message=self._{{ inst_id }}_data
        ))
        {% endfor %}

    # ---- Callbacks ----
    {%- for p in placements %}
        {%- set ref = p.ref %}
        {%- set subclass = ref.__class__.__name__ | lower -%}
        {%- set inst_id = (ref.name | lower) ~ '_1' %}

    def _{{ inst_id }}_pose(self, msg: PoseMessage):
        x = float(msg.position.get('x', 0.0))
        y = float(msg.position.get('y', 0.0))
        yaw = float(msg.orientation.get('yaw', 0.0))
        self.poses[("{{ subclass }}", "{{ inst_id }}")] = {'x': x, 'y': y, 'theta': yaw}
        print(f"[Environment] Pose [{{ subclass }}/{{ inst_id }}] -> x={x:.2f}, y={y:.2f}, theta={yaw:.1f}")

    def _{{ inst_id }}_data(self, msg: PubSubMessage):
        payload = msg.model_dump() if hasattr(msg, "model_dump") else dict(getattr(msg, "__dict__", {}))
        self.data[("{{ subclass }}", "{{ inst_id }}")] = payload
        print(f"[Environment] Data [{{ subclass }}/{{ inst_id }}]  payload={payload}")
    {% endfor %}

    def start(self):
        # Launch commlib internal loop in a background thread
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print("[Environment] Running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)  # keep main thread alive
        except KeyboardInterrupt:
            print("[Environment] Interrupted by user.")
            self.stop()

if __name__ == '__main__':
    try:
        redis.Redis(host='localhost', port=6379).ping()
        print("[Redis] Connected successfully.")
    except redis.exceptions.ConnectionError:
        print("[Redis] Not running. Start Redis server first.")
        sys.exit(1)

    node = EnvironmentNode(env_name="{{ environment.name }}")
    try:
        node.start()
    except KeyboardInterrupt:
        print(f"\n[{{ environment.name }}] Stopped by user.")
        node.stop()
