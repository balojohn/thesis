from commlib.msg import PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
import time


class TemperatureMessage(PubSubMessage):
    sensor_id: str
    location: str
    temperature: float
    range: float


class TemperatureSensor:
    def __init__(self, sensor_id: str):
        self.sensor_id = sensor_id
        self.conn_params = ConnectionParameters()
        self.node = Node(node_name=f"sensors.temperature.{sensor_id}",
                         connection_params=self.conn_params)

        self.subscriber = self.node.create_subscriber(
            msg_type=TemperatureMessage,
            topic=f"sensors.temperature.{sensor_id}",
            on_message=self.on_temperature_received
        )

    def on_temperature_received(self, msg: TemperatureMessage):
        print(f"[Sensor] Received temperature: {msg.temperature}°C from {msg.location}")

    def run(self):
        self.node.run()


if __name__ == "__main__":
    try:
        sensor = TemperatureSensor(sensor_id="sensor_1")
        sensor.run()
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[Sensor] Stopped by user.")
        sensor.node.stop()
