import pytest
from omnisim.generated_files.environments.home import HomeNode


@pytest.fixture
def node():
    return HomeNode("Home")

def test_update_sensor_pose(node):
    node.node_pose_callback({
        "class": "sensor",
        "type": "envsensor",
        "name": "temperature",
        "id": "te_1",
        "x": node.poses["sensors"]["envsensor"]["temperature"]["te_1"]["x"],
        "y": node.poses["sensors"]["envsensor"]["temperature"]["te_1"]["y"],
        "theta": node.poses["sensors"]["envsensor"]["temperature"]["te_1"]["theta"],
    })
    pose = node.poses["sensors"]["envsensor"]["temperature"]["te_1"]
    assert pose == {"x": 6.0, "y": 1.0, "theta": 0.0}