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
    }, parent_pose=None)
    pose = node.poses["sensors"]["envsensor"]["temperature"]["te_1"]
    
    expected = {"x": 520.0, "y": 415.0, "theta": -180}
    for k, v in expected.items():
        assert pose[k] == pytest.approx(v, abs=1e-3)


    # Optionally confirm that shape exists and is correct
    assert "shape" in pose
    assert pose["shape"]["type"].lower() == "circle"
    assert pose["shape"]["radius"] == pytest.approx(3.0, abs=1e-3)