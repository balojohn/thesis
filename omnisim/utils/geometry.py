# utils/geometry.py
from commlib.msg import PubSubMessage

class PoseMessage(PubSubMessage):
    """2D pose message."""
    x: float
    y: float
    theta: float