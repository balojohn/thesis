{% if thing.noise %}
import random
{% endif %}
import sys
import threading
import subprocess
import time
import redis
import os
from commlib.msg import MessageHeader, PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate

# Path to your redis-server executable
REDIS_PATH = r"C:\redis\redis-server.exe"

{% set id_field = "sensor_id" %}
{% if thing.class == "Actuator" %}
{% set id_field = "actuator_id" %}
{% elif thing.class == "Actor" %}
{% set id_field = "actor_id" %}
{% endif %}

{% set class_prefix = thing.class.lower() %}
{% set subclass = thing.__class__.__name__.lower() %}
{% set type = thing.type.lower() %}
{% set topic_base = class_prefix + '.' + subclass + '.' + type %}

{% set node_prefix =
    "sensor." if thing.class == "Sensor"
    else "actuator." if thing.class == "Actuator"
    else "actor."
%}
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
{% if endpoint.topic.startswith(node_prefix) %}
{% set msg = endpoint.msg %}
{% if msg %}
class {{ msg.name }}(PubSubMessage):
    {# Combine properties from the comm message and the data model #}
    {% set msg_props = msg.properties + dataModel.properties %}
    {% for prop in msg_props | unique(attribute='name') %}
    {{ prop.name }}: {{ "float" if prop.type.name == "float" else "str" }}
    {% endfor %}
{% endif %}
{% endif %}
{% endfor %}
{% endfor %}

class {{ thing.name }}Node(Node):
    def __init__(self, {{ id_field }}: str = "", *args, **kwargs):
        self.pub_freq = {{ thing.pubFreq }}
        self.{{ id_field }} = {{ id_field }}
        {% for prop in dataModel.properties %}
        self.{{ prop.name }} = {{ thing[prop.name] }}
        {% endfor %}

        conn_params = ConnectionParameters()

        super().__init__(
            node_name="{{ thing.name.lower() }}",
            connection_params=conn_params,
            *args, **kwargs
        )

        {% for comm in comms.communications %}
        {% for e in comm.endpoints %}
        {% if e.__class__.__name__ == "Publisher" and e.topic.startswith(node_prefix) %}
        # Create dedicated publisher for {{ e.topic }}
        self.publisher = self.create_publisher(
            topic=f"{{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}",
            msg_type={{ e.msg.name }},
        )
        {% endif %}
        {% endfor %}
        {% endfor %}

    def simulate_{{ type }}(self):
        # TODO: implement actual simulation logic for {{ thing.type }}
        return 0.0

    def start(self):
        # Start commlib's internal loop in the background (since run() is blocking)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print(f"[{self.__class__.__name__}] Running with id={self.{{ id_field }}}")
        rate = Rate(self.pub_freq)
        while True:
            {% for comm in comms.communications %}
            {% for e in comm.endpoints %}
            {% if e.__class__.__name__ == "Publisher" and e.topic.startswith(node_prefix) %}
            # create the message
            msg = {{ e.msg.name }}(
                pubFreq=self.pub_freq,
                {{ id_field }}=self.{{ id_field }},
                type="{{ thing.dataModel.name }}",
                {% for prop in dataModel.properties %}
                {% if prop.name == "range" or prop.name == "distance" %}
                {% if thing.noise %}
                {{ prop.name }} = round(random.gauss(self.simulate_{{ type }}(), {{ thing.noise.std }}), 2),
                {% else %}
                {{ prop.name }} = self.simulate_{{ type }}(),
                {% endif %}
                {% else %}
                {{ prop.name }} = self.{{ prop.name }},
                {% endif %}
                {% endfor %}
            )
            print(f"[{{ thing.name }}Node] Publishing to {{ topic_base }}.{{ '{self.' ~ id_field ~ '}' }}: {msg.model_dump()}")
            self.publisher.publish(msg)
            {% endif %}
            {% endfor %}
            {% endfor %}
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.sonar sonar_2
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
        {{ id_field }} = sys.argv[1] if len(sys.argv) > 1 else "{{ thing.name.lower() }}_1"
        node = {{ thing.name }}Node({{ id_field }}={{ id_field }})
        node.start()
    except KeyboardInterrupt:
        print(f"\n[{{ thing.name }}] Stopped by user.")
        node.stop()