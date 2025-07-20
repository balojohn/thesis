import time
import random

from commlib.msg import PubSubMessage
from commlib.node import Node
from commlib.transports import TransportType as transport_type
from commlib.transports.redis import ConnectionParameters


# ====== Message Class ======
# class TemperatureMessage(PubSubMessage):
#     #     temperature: float
#     #     range: float
#     #     location: str
#     
# ====== Sensor Node ======
class TemperatureSensorA(Node):
    def __init__(self):
        self.sensor_id = 'TemperatureSensorA'
        self.sensor_type = 'sensor'
        self.topic = 'actor.thermostat.thA'
        self.pub_freq = 1
        self.conn_params = ConnectionParameters()
        self.node_name = f'sensor.{self.sensor_type}.{self.sensor_id}'

        self.node = Node(node_name=self.node_name,
                connection_params=self.conn_params)
        
        self.subscriber = self.node.create_subscriber(
            msg_type=TemperatureMessage,
            topic=self.topic,
            on_message=self.on_message
        )

    def on_message(self, msg: TemperatureMessage):
        print(f"[TemperatureSensorA] Received message: {msg.__dict__}")
    
    def run(self):
        self.node.run()

if __name__ == '__main__':
    try:
        sensor = TemperatureSensorA()
        sensor.node.run()
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n[{sensor.sensor_id}] Stopped by user.")
        sensor.node.stop()