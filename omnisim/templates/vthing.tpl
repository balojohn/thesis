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

def start_redis():
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
{% set msg = endpoint.msg %}
{% if msg %}
class {{ msg.name }}(PubSubMessage):
    {% for prop in msg.properties %}
    {{ prop.name }}: {{ "float" if prop.type.name == "float" else "str" }}
    {% endfor %}
{% endif %}
{% endfor %}
{% endfor %}

class {{ thing.name }}Node(Node):
    def __init__(self, sensor_id: str = "", *args, **kwargs):
        self.pub_freq = {{ thing.pubFreq }}
        self.sensor_id = sensor_id
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="{{ thing.name.lower() }}",
            connection_params=conn_params,
            *args, **kwargs
        )

        {% for comm in comms.communications %}
        {% for e in comm.endpoints %}
        {% if e.__class__.__name__ == "Publisher" %}
        # Create dedicated publisher for {{ e.uri }}
        self.{{ e.uri.replace('.', '_') }}_pub = self.create_publisher(
            topic='{{ e.uri }}',
            msg_type={{ e.msg.name }},
        )
        {% endif %}
        {% endfor %}
        {% endfor %}

    def start(self):
        # Start commlib's internal loop in the background (since run() is blocking)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(0.5)  # Give commlib time to initialize the transport
        print(f"[{self.__class__.__name__}] Running with sensor_id={self.sensor_id}")
        rate = Rate(self.pub_freq)
        while True:
            {% for comm in comms.communications %}
            {% for e in comm.endpoints %}
            {% if e.__class__.__name__ == "Publisher" %}
            # create the message
            msg = {{ e.msg.name }}(
                pubFreq=self.pub_freq,
                sensor_id=self.sensor_id,
                type="RangeData"
            )
            print(f"[{{ thing.name }}Node] Publishing to {{ e.uri }}: {msg.model_dump()}")
            self.{{ e.uri.replace('.', '_') }}_pub.publish(msg)
            {% endif %}
            {% endfor %}
            {% endfor %}
            rate.sleep()

# Run it from C:\thesis\ by: python -m omnisim.generated_files.sonar sonar_2
if __name__ == '__main__':
    start_redis()
    try:
        try:
            r = redis.Redis(host='localhost', port=6379)
            r.ping()
            print("[Redis] Connected successfully.")
        except redis.exceptions.ConnectionError:
            print("[Redis] Not running. Start Redis server first.")
            exit(1)
        sensor_id = sys.argv[1] if len(sys.argv) > 1 else "{{ thing.name.lower() }}_1"
        node = {{ thing.name }}Node(sensor_id=sensor_id)
        node.start()
    except KeyboardInterrupt:
        print(f"\n[{{ thing.name }}] Stopped by user.")
        node.stop()