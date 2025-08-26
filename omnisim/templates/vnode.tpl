import random
import math
import sys
import threading
import subprocess
import time
import redis
# import os
from commlib.msg import PubSubMessage # MessageHeader
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate
from ..utils import Dispersion

{% set obj = thing if thing is defined else actor %}
{%- set class_prefix = obj.class.lower() %}
{%- set subclass = obj.__class__.__name__.lower() %}
{% if obj.type is defined %}
    {%- set type = obj.type.lower() %}
    {%- set topic_base = class_prefix + '.' + subclass + '.' + type %}
{% else %}
    {%- set topic_base = class_prefix + '.' + subclass %}
{% endif %}
{%- set topic_base = class_prefix + '.' + subclass ~ ('.' ~ obj.type.lower() if obj.type is defined else '') %}
{%- set node_prefix =
    "sensor." if obj.class == "Sensor"
    else "actuator." if obj.class == "Actuator"
    else "actor."
%}
{# Definitions only for use in jinja #}
{% if obj.class == "Sensor" %}
    {%- set id_field = "sensor_id" %}
{% elif obj.class == "Actuator" %}
    {%- set id_field = "actuator_id" %}
{% else %}
    {%- set id_field = "actor_id" %}
{% endif %}

{%- macro pytype(typename) -%}
    {%- if typename == "float" -%}float
    {%- elif typename == "int" -%}int
    {%- elif typename == "bool" -%}bool
    {%- else -%}str
    {%- endif -%}
{%- endmacro %}

{%- set prop_values = {} %}
{% if obj.__class__.__name__ == "EnvActor" %}
    {% for p in obj.EnvProperties %}
        {% set _ = prop_values.update({p.name: p.value}) %}
    {% endfor %}
{% else %}
    {% for prop in dataModel.properties %}
        {% if obj[prop.name] is defined %}
            {% set _ = prop_values.update({prop.name: obj[prop.name]}) %}
        {% endif %}
    {% endfor %}
{% endif -%}

# Path to your redis-server executable
REDIS_PATH = r"C:\redis\redis-server.exe"
def redis_start():
    print("[System] Starting Redis server...")
    try:
        proc = subprocess.Popen([REDIS_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)  # give Redis a moment to start
        r = redis.Redis(host='localhost', port=6379)
        if r.ping():
            print("[System] Redis is now running.")
            return proc
    except Exception as e:
        print(f"[ERROR] Could not start Redis: {e}")
        sys.exit(1)

{% for comm in comms.communications %}
    {% for endpoint in comm.endpoints %}
        {% if endpoint.__class__.__name__ == "Publisher" and endpoint.topic.startswith(topic_base) %}
            {% set msg = endpoint.msg %}
            {% if msg %}
class {{ msg.name }}(PubSubMessage):
    {% for prop in msg.properties | unique(attribute='name') %}
    {{ prop.name }}: {{ pytype(prop.type.name) }}
    {% endfor %}
            {% else %}
# [WARN] No message found for topic '{{ topic_base }}'
            {% endif %}
        {% endif %}
    {% endfor %}
{% endfor %}

SIMULATED_PROPS = {
{#
    {% if obj.__class__.__name__ == "EnvActor" %}
        {% for prop in dataModel.properties if prop.type.name != "str" %}
    "{{ prop.name }}",
        {% endfor %}
    {% elif obj.name == "Sonar" %}
        {% for prop in dataModel.properties %}
    "{{ prop.name }}",
        {% endfor %}
    {% endif %}
#}
    {% for prop in dataModel.properties %}
    "{{ prop.name }}",
    {% endfor %}
}

class {{ obj.name }}Node(Node):
    def __init__(self, {{ id_field }}: str = "", *args, **kwargs):
        self.pub_freq = {{ obj.pubFreq }}
        {% if obj.dispersion %}
        self.dispersion = Dispersion(
            "{{ obj.dispersion.__class__.__name__ }}",{{ '\n' }}
            {%- for attr, val in obj.dispersion.__dict__.items() if attr not in ['_tx_model', '_tx_position', '_tx_position_end', 'parent'] %}
            {{ attr }}={{ val }},{{ '\n' }}
            {%- endfor %}
        )
        {% else %}
        self.dispersion = None
        {% endif %}
        self.{{ id_field }} = {{ id_field }}
        {% for prop in dataModel.properties %}
        {% set val = prop_values.get(prop.name) %}
        {% if prop.type.name == "str" %}
        self.{{ prop.name }} = {{ '"' ~ (val | string | replace('"', '\\"')) ~ '"' if val is not none else '""' }}
        {% else %}
        self.{{ prop.name }} = {{ val if val is not none else 0.0 }}
        {% endif %}
        {% endfor %}
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="{{ obj.name.lower() }}",
            connection_params=conn_params,
            *args, **kwargs
        )

        {% for comm in comms.communications %}
        {% for e in comm.endpoints %}
        {% if e.__class__.__name__ == "Publisher" and e.topic == topic_base %}
        # Create dedicated publisher for {{ e.topic }}
        self.publisher = self.create_publisher(
            topic=f"{{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}",
            msg_type={{ e.msg.name }},
        )
        {% endif %}
        {% endfor %}
        {% endfor %}

    def simulate_{{ obj.name.lower() }}(self, name: str):
        """
        Simulate dynamic behavior for '{{ obj.name }}' actor.
        """
        t = time.time()

        {% if obj.name == "Sonar" %}
        # Simulate range oscillation (Sonar)
        amplitude = (self.maxRange - self.minRange) / 2
        center = (self.maxRange + self.minRange) / 2
        wave = amplitude * math.sin(t)
        base = center + wave
        return max(self.minRange, min(self.maxRange, base))

        {% elif obj.name == "Fire" %}
        # Simulate fire behavior (temperature, luminosity, co2)
        if not hasattr(self, "_sim_state"):
            self._sim_state = {
                "temperature": self.temperature,
                "luminosity": self.luminosity,
                "co2": self.co2,
            }

        if name == "temperature":
            delta = random.uniform(5, 20)
            self._sim_state["temperature"] = min(1000.0, self._sim_state["temperature"] + delta)
            temp = self._sim_state["temperature"]
            return self.dispersion.apply(temp) if self.dispersion else temp

        elif name == "luminosity":
            fluct = random.uniform(-20, 50)
            new_val = max(0.0, min(500.0, self._sim_state["luminosity"] + fluct))
            self._sim_state["luminosity"] = new_val
            return new_val

        elif name == "co2":
            delta = random.uniform(50, 200)
            self._sim_state["co2"] = min(10000.0, self._sim_state["co2"] + delta)
            return self._sim_state["co2"]

        {% else %}
        # Default fallback
        if hasattr(self, name):
            base = getattr(self, name)
            {% if obj.name == "Color" %}
            if name in {"r", "g", "b"}:
                return max(0, min(255, int(random.gauss(base, 30.0))))
            {% endif %}
            if isinstance(base, (int, float)):
                return random.gauss(base, 1.0)
            elif isinstance(base, str):
                # Example: rotate dynamic messages
                choices = ["Hello", "World", "Barcode", "Active", "Scan"]
                return random.choice(choices)
        {% endif %}

    def get_property_value(self, name):
        if name in SIMULATED_PROPS:
            val = self.simulate_{{ obj.name.lower() }}(name)
            if isinstance(val, (int, float)):
                {% if obj.name == "Color" %}
                if name in {"r", "g", "b"}:
                    return max(0, min(255, int(val)))
                {% endif %}
                {% if obj.name == "Human" %}
                if name in {"age"}:
                    return max(0, int(val))
                {% endif %}
                {% if obj.noise %}
                return round(random.gauss(val, {{ obj.noise.std }}), 2)
                {% else %}
                return round(val, 2)
                {% endif %}
            else:
                return val
        if hasattr(self, name):
            return getattr(self, name)

    def start(self):
        # Start commlib's internal loop in the background (since run() is blocking)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print(f"[{self.__class__.__name__}] Running with id={self.{{ id_field }}}")
        rate = Rate(self.pub_freq)
        while True:
            # DEBUG: topic_base = {{ topic_base }}
            {% for comm in comms.communications %}
            {% for e in comm.endpoints %}
            # DEBUG: endpoint = {{ e.__class__.__name__ }}, topic = {{ e.topic }}
            {% endfor %}
            {% endfor %}
            {% for comm in comms.communications %}
            {% for e in comm.endpoints %}
            {% if e.__class__.__name__ == "Publisher" and e.topic == topic_base %}
            msg = {{ e.msg.name }}(
                pubFreq=self.pub_freq,
                {{ id_field }}=self.{{ id_field }},
                type="{{ obj.dataModel.name }}",
                {% for prop in dataModel.properties %}
                {% if pytype(prop.type.name) == "int" %}
                {{ prop.name }}=int(self.get_property_value("{{ prop.name }}")),
                {% elif pytype(prop.type.name) == "float" %}
                {{ prop.name }}=float(self.get_property_value("{{ prop.name }}")),
                {% elif pytype(prop.type.name) == "str" %}
                {{ prop.name }}=str(self.get_property_value("{{ prop.name }}")),
                {% endif %}
                {% endfor %}
            )
            print(f"[{{ obj.name }}Node] Publishing to {{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}: {msg.model_dump()}")
            self.publisher.publish(msg)
            {% endif %}
            {% endfor %}
            {% endfor %}
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.{{ obj.name.lower() }} name
if __name__ == '__main__':
    redis_start()
    try:
        try:
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            print("[Redis] Connected successfully.")
        except redis.exceptions.ConnectionError:
            print("[Redis] Not running. Start Redis server first.")
            exit(1)
        {{ id_field }} = sys.argv[1] if len(sys.argv) > 1 else "{{ obj.name.lower() }}_1"
        node = {{ obj.name }}Node({{ id_field }}={{ id_field }})
        node.start()
    except KeyboardInterrupt:
        print(f"\n[{{ obj.name }}] Stopped by user.")
        node.stop()