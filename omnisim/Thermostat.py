import time
import random

from commlib.msg import PubSubMessage
from commlib.node import Node
# from commlib.transports import TransportType as transport_type
from commlib.transports.redis import ConnectionParameters

# ====== Message Class ======
class TemperatureMessage(PubSubMessage):
    temperature: float
    range: float
    location: str

# ====== Actor Node ======
class Thermostat(Node):
    def __init__(self):
        self.actor_id = 'Thermostat'
        self.actor_type = 'actor'
        self.topic = 'actor.thermostat.thA'
        self.msg = TemperatureMessage
        self.conn_params = ConnectionParameters()
        self.node_name = 'actor.Thermostat'
        self.node = Node(node_name=self.node_name,
                    connection_params=self.conn_params)
        self.publisher = self.node.create_publisher(
            msg_type=TemperatureMessage,
            topic=self.topic
        )
        self.node.run()

    def generate_temperature(self, TemperatureMessage):
        TemperatureMessage.temperature = round(random.uniform(-20.0, 50.0), 2)
        TemperatureMessage.range = 10.0
        TemperatureMessage.location = 'Living Room'

    def publish_temperature(self, TemperatureMessage):
        self.generate_temperature(TemperatureMessage)
        print(f"[Thermostat] Publishing temperature: {TemperatureMessage.temperature} degC from {TemperatureMessage.location}")
        self.publisher.publish(TemperatureMessage)

if __name__ == '__main__':
    try:
        actor = Thermostat()
        actor.node.run()
    
        while True:
            msg = TemperatureMessage(temperature=0.0, range=0.0, location='')
            actor.publish_temperature(msg)
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n[{actor.actor_id}] Stopped by user.")
        actor.node.stop()