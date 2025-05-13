import time
import random

from commlib.msg import PubSubMessage
from commlib.node import Node
from commlib.transports import TransportType as transport_type
from commlib.transports.redis import ConnectionParameters

# ====== Message Class ======
class {{ message_name }}(PubSubMessage):
    {% for prop in message_properties %}
    {{ prop.name }}: {{ prop.type }}
    {% endfor %}

# ====== Actor Node ======
class {{ actor_name }}(Node):
    def __init__(self):
        self.actor_id = '{{ actor_id }}'
        self.actor_type = '{{ actor_type }}'
        self.topic = '{{ actor_topic }}'
        self.msg = {{ message_name }}
        self.conn_params = ConnectionParameters()
        self.node_name = '{{ actor_type }}.{{ actor_id }}'
        self.node = Node(node_name=self.node_name,
                    connection_params=self.conn_params)
        self.publisher = self.node.create_publisher(
            msg_type={{ message_name }},
            topic=self.topic
        )
        self.node.run()

    def generate_temperature(self, {{ message_name }}):
        {{ message_name }}.{{ message_properties[0].name }} = round(random.uniform(-20.0, 50.0), 2)
        {{ message_name }}.{{ message_properties[1].name }} = 10.0
        {{ message_name }}.{{ message_properties[2].name }} = 'Living Room'

    def publish_temperature(self, {{ message_name }}):
        self.generate_temperature({{ message_name }})
        print(f"[{{ actor_name }}] Publishing temperature: {{ '{' }}{{ message_name }}.{{ message_properties[0].name }}{{ '}' }} degC from {{ '{' }}{{ message_name }}.{{ message_properties[2].name }}{{ '}' }}")
        self.publisher.publish({{ message_name }})

if __name__ == '__main__':
    try:
        actor = {{ actor_name }}()
        actor.node.run()
    
        while True:
            msg = {{ message_name }}({{ message_properties[0].name }}=0.0, {{ message_properties[1].name }}=0.0, {{ message_properties[2].name }}='')
            actor.publish_temperature(msg)
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{actor}] Stopped by user.")
        actor.node.stop()