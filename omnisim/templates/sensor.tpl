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

# ====== Sensor Node ======
class {{ sensor_name }}(Node):
    def __init__(self):
        self.sensor_id = '{{ sensor_id }}'
        self.sensor_type = '{{ sensor_type }}'
        self.topic = '{{ sensor_topic }}'
        self.pub_freq = {{ pub_freq }}
        self.conn_params = ConnectionParameters()
        self.node_name = f'sensor.{self.sensor_type}.{self.sensor_id}'

        self.node = Node(node_name=self.node_name,
                connection_params=self.conn_params)
        
        self.subscriber = self.node.create_subscriber(
            msg_type={{ message_name }},
            topic=self.topic,
            on_message=self.on_message
        )

    def on_message(self, msg: {{ message_name }}):
        print(f"[{{ sensor_name }}] Received message: {msg.__dict__}")
    
    def run(self):
        self.node.run()

if __name__ == '__main__':
    try:
        sensor = {{ sensor_name }}()
        sensor.node.run()
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n[{sensor.sensor_id}] Stopped by user.")
        sensor.node.stop()
