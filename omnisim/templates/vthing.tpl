from commlib.msg import MessageHeader, PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate

{% set dModels = [] %}
{% for msg in communication.msgs %}
{% if msg.name not in dModels %}
{% if msg.__class__.__name__ == "PubSubMessage" %}
class {{ msg.name }}(PubSubMessage):
    {% for p in msg.properties %}
    {{ p.name }}: {{ p.type.name }}
    {% endfor %}
{% endif %}
{% set dModels = dModels.append(msg.name) %}
{% endif %}
{% endfor %}

class {{ thing.name }}Node(Node):
    def __init__(self, *args, **kwargs):
        self.pub_freq = {{ thing.pubFreq }}
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="{{ thing.name.lower() }}",
            connection_params=conn_params,
            *args, **kwargs
        )

        {% for e in communication.endpoints %}
        {% if e.__class__.__name__ == "Subscriber" %}
        self.create_subscriber(
            '{{ e.uri }}',
            {{ e.msg.name }},
            on_message=self.{{ e.uri.split('.')[-1] }}
        )

        {% elif e.__class__.__name__ == "Publisher" %}
        self.pub = self.create_publisher(
            '{{ e.uri }}',
            {{ e.msg.name }},
        )
        {% endif %}
        {% endfor %}

    def start(self):
        self.run()
        {% for e in communication.endpoints %}
        {% if e.__class__.__name__ == "Publisher" %}
        self.pub.publish({{ e.msg.name }}(
            {% for p in e.msg.properties %}
            {{ p.name }}={{ thing[p.name] }},
            {% endfor %}
        ))
        {% endif %}
        {% endfor %}
        rate = Rate(self.pub_freq)
        while True:
            rate.sleep()

if __name__ == '__main__':
    try:
        node = {{ thing.name }}Node()

        node.start()
    except KeyboardInterrupt:
        print(f"\n[{{ thing.name }}] Stopped by user.")
        node.stop()
