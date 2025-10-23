import pytest
from omnisim.generated_files.environments.home import HomeNode

@pytest.fixture
def node():
    return HomeNode("Home")

def test_temperature_sensor_detects_thermostat(node):
    """Temperature sensor should detect nearby thermostat within range."""
    print(f"DEBUG ---> {node.poses["sensors"]["envsensor"]["temperature"]["te_1"]}")
    print(f"DEBUG ---> {node.poses["actuators"]["envdevice"]["thermostat"]["th_1"]}")
    temperatures = node.handle_temperature_sensor("te_1")
    assert "th_1" in temperatures

    th = temperatures["th_1"]
    # Check distance: sensor(520, 415, -180) -> thermostat(500, 415) = 20.0
    assert th["distance"] == pytest.approx(20, abs=1e-2)
    # Check merged property from actuator definition
    assert th["target_value"] == 25.0
    # Name and ID from node metadata
    assert th["subtype"] == "thermostat"
    assert th["name"] == "th_1"
    # Class should be actuator
    assert th["class"] == "actuator"


# def test_temperature_sensor_detects_fire(node):
#     """Temperature sensor should detect nearby fire within range."""
#     aff = node.handle_temperature_sensor("te_1")
#     assert "fi_1" in aff

#     fi = aff["fi_1"]
#     # Check distance: sensor(6,1) -> fire(6,3) = 2.0
#     assert fi["distance"] == pytest.approx(2, abs=1e-2)
#     # Property merged from actor definition
#     assert fi["value"] == 1000.0
#     # Name and ID from node metadata
#     assert fi["name"] == "fire"
#     assert fi["id"] == "fi_1"
#     # Class should be actor
#     assert fi["class"] == "actor"

# def test_humidity_sensor_detects_humidifier(node):
#     """Humidity sensor should detect nearby humidifier within range."""
#     temperatures = node.handle_humidity_sensor("hum_1")
#     assert "humact_1" in temperatures

#     humact = temperatures["humact_1"]
#     # Check distance: sensor(2,1) -> humidifier(1,1) = 1.0
#     assert humact["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Check merged property from actuator definition
#     assert humact["target_value"] == 25.0
#     # Name and ID from node metadata
#     assert humact["name"] == "humidifier"
#     assert humact["id"] == "humact_1"
#     # Class should be actuator
#     assert humact["class"] == "actuator"

# def test_humidity_sensor_detects_water(node):
#     """Humidity sensor should detect nearby water within range."""
#     aff = node.handle_humidity_sensor("hum_1")
#     assert "wa_1" in aff

#     wa = aff["wa_1"]
#     # Check distance: sensor(2,1) -> water(5,5) = sqrt(3^2 + 4^2) = 5.0
#     assert wa["distance"] == pytest.approx(5.0, abs=1e-2)
#     # Property merged from actor definition
#     assert wa["value"] == 100.0
#     # Name and ID from node metadata
#     assert wa["name"] == "water"
#     assert wa["id"] == "wa_1"
#     # Class should be actor
#     assert wa["class"] == "actor"

# def test_gas_sensor_detects_fire(node):
#     """Gas sensor should detect nearby fire within range."""
#     aff = node.handle_gas_sensor("gas_1")
#     assert "fi_1" in aff

#     fi = aff["fi_1"]
#     # Check distance: sensor(6,2) -> fire(6,3) = 1.0
#     assert fi["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Property merged from actor definition
#     assert fi["value"] == 1000.0
#     # Name and ID from node metadata
#     assert fi["name"] == "fire"
#     assert fi["id"] == "fi_1"
#     # Class should be actor
#     assert fi["class"] == "actor"

# def test_gas_sensor_detects_human(node):
#     """Gas sensor should detect nearby human within range."""
#     aff = node.handle_gas_sensor("gas_1")
#     assert "hu_1" in aff

#     hu = aff["hu_1"]
#     # Check distance: sensor(6,2) -> human(6,1) = 1.0
#     assert hu["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Name and ID from node metadata
#     assert hu["name"] == "human"
#     assert hu["id"] == "hu_1"
#     # Class should be actor
#     assert hu["class"] == "actor"

# def test_microphone_sensor_detects_speaker(node):
#     """Microphone sensor should detect nearby speaker within range."""
#     aff = node.handle_microphone_sensor("mic_1")
#     assert "speak_1" in aff

#     speak = aff["speak_1"]
#     # Check distance: sensor(8,8) -> speaker(8,9) = 1.0
#     assert speak["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Name and ID from node metadata
#     assert speak["name"] == "speaker"
#     assert speak["id"] == "speak_1"
#     # Class should be actor
#     assert speak["class"] == "actuator"

# def test_microphone_sensor_detects_human(node):
#     """Microphone sensor should detect nearby human within range."""
#     aff = node.handle_microphone_sensor("mic_1")
#     assert "hu_1" in aff

#     hu = aff["hu_1"]
#     # Check distance: sensor(8,8) -> human(6,1) = sqrt(2^2 + 7^2) = 7.28
#     assert hu["distance"] == pytest.approx(7.28, abs=1e-2)
#     # Name and ID from node metadata
#     assert hu["name"] == "human"
#     assert hu["id"] == "hu_1"
#     # Class should be actor
#     assert hu["class"] == "actor" 

# def test_microphone_sensor_detects_soundsource(node):
#     """Microphone sensor should detect nearby soundsource within range."""
#     aff = node.handle_microphone_sensor("mic_1")
#     assert "sou_1" in aff

#     sou = aff["sou_1"]
#     # Check distance: sensor(6,2) -> human(6,1) = 1.0
#     assert sou["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Name and ID from node metadata
#     assert sou["name"] == "soundsource"
#     assert sou["id"] == "sou_1"
#     # Class should be actor
#     assert sou["class"] == "actor"

# def test_light_sensor_detects_led(node):
#     """Light sensor should detect nearby led within range."""
#     aff = node.handle_light_sensor("li_1")
#     assert "led_1" in aff

#     led = aff["led_1"]
#     # Check distance: sensor(6,2) -> led(6,4) = 2.0
#     assert led["distance"] == pytest.approx(2.0, abs=1e-2)
#     # Name and ID from node metadata
#     assert led["name"] == "led"
#     assert led["id"] == "led_1"
#     # Class should be actor
#     assert led["class"] == "actuator"

# def test_light_sensor_detects_fire(node):
#     """Light sensor should detect nearby fire within range."""
#     aff = node.handle_light_sensor("li_1")
#     assert "fi_1" in aff

#     fi = aff["fi_1"]
#     # Check distance: sensor(6,2) -> fire(6,3) = 1.0
#     assert fi["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Name and ID from node metadata
#     assert fi["name"] == "fire"
#     assert fi["id"] == "fi_1"
#     # Class should be actor
#     assert fi["class"] == "actor"

# def test_camera_sensor_detects_human(node):
#     """Camera sensor should detect nearby human within range."""
#     aff = node.handle_camera_sensor("cam_1", with_robots=False)
#     assert "hu_1" in aff

#     hu = aff["hu_1"]
#     # Check distance: sensor(2,6) -> human(6,1) = sqrt(4^2 + 5^2) = 6.40
#     assert hu["distance"] == pytest.approx(6.40, abs=1e-2)
#     # Name and ID from node metadata
#     assert hu["name"] == "human"
#     assert hu["id"] == "hu_1"
#     # Class should be actor
#     assert hu["class"] == "actor"

# def test_camera_sensor_detects_qr(node):
#     """Camera sensor should detect nearby qrcode within range."""
#     aff = node.handle_camera_sensor("cam_1", with_robots=False)
#     assert "qr_1" in aff

#     qr = aff["qr_1"]
#     # Check distance: sensor(2,6) -> qrcode(1, 6) = 1.0
#     assert qr["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Name and ID from node metadata
#     assert qr["name"] == "qrcode"
#     assert qr["id"] == "qr_1"
#     # Class should be actor
#     assert qr["class"] == "actor"

# def test_camera_sensor_detects_barcode(node):
#     """Camera sensor should detect nearby barcode within range."""
#     aff = node.handle_camera_sensor("cam_1", with_robots=False)
#     assert "bar_1" in aff

#     bar = aff["bar_1"]
#     # Check distance: sensor(2,6) -> barcode(1,7) = sqrt(1^2 + 1^2) = 1.41
#     assert bar["distance"] == pytest.approx(1.41, abs=1e-2)
#     # Name and ID from node metadata
#     assert bar["name"] == "barcode"
#     assert bar["id"] == "bar_1"
#     # Class should be actor
#     assert bar["class"] == "actor"

# def test_camera_sensor_detects_plaintext(node):
#     """Camera sensor should detect nearby plaintext within range."""
#     aff = node.handle_camera_sensor("cam_1", with_robots=False)
#     assert "txt_1" in aff

#     txt = aff["txt_1"]
#     # Check distance: sensor(2,6) -> text(1,10) = sqrt(1^2 + 4^2) = 4.12
#     assert txt["distance"] == pytest.approx(4.12, abs=1e-2)
#     # Name and ID from node metadata
#     assert txt["name"] == "plaintext"
#     assert txt["id"] == "txt_1"
#     # Class should be actor
#     assert txt["class"] == "actor"

# def test_camera_sensor_detects_color(node):
#     """Camera sensor should detect nearby color within range."""
#     aff = node.handle_camera_sensor("cam_1", with_robots=False)
#     assert "col_1" in aff

#     col = aff["col_1"]
#     # Check distance: sensor(2,6) -> color(1,11) = sqrt(1^2 + 5^2) = 5.09
#     assert col["distance"] == pytest.approx(5.09, abs=1e-2)
#     # Name and ID from node metadata
#     assert col["name"] == "color"
#     assert col["id"] == "col_1"
#     # Class should be actor
#     assert col["class"] == "actor"

# def test_camera_sensor_detects_led(node):
#     """Camera sensor should detect nearby led within range."""
#     aff = node.handle_camera_sensor("cam_1", with_robots=False)
#     assert "led_1" in aff

#     led = aff["led_1"]
#     # Check distance: sensor(2,6) -> led(6,4) = sqrt(4^2 + 2^2) = 4.47
#     assert led["distance"] == pytest.approx(4.47, abs=1e-2)
#     # Name and ID from node metadata
#     assert led["name"] == "led"
#     assert led["id"] == "led_1"
#     # Class should be actor
#     assert led["class"] == "actuator"

# def test_rfid_sensor_detects_rfid_tags(node):
#     """Rfid sensor should detect nearby rfid tags within range."""
#     aff = node.handle_rfid_sensor("rfid_1")
#     assert "rf_1" in aff

#     rf = aff["rf_1"]
#     # Check distance: sensor(12,12) -> rfidtag(12,13) = 1.0
#     assert rf["distance"] == pytest.approx(1.0, abs=1e-2)
#     # Name and ID from node metadata
#     assert rf["name"] == "rfidtag"
#     assert rf["id"] == "rf_1"
#     # Class should be actor
#     assert rf["class"] == "actor"

# def test_areaalarm_sensor_detects_robot(node):
#     """Area alarm sensor should detect nearby robots within range."""
#     aff = node.handle_area_alarm("aral_1")
#     assert "r_1" in aff

#     rob = aff["r_1"]
#     # Check distance: sensor(15,15) -> robot(8,13) = sqrt(7^2 + 2^2) = 7.28
#     assert rob["distance"] == pytest.approx(7.28, abs=1e-2)
#     # Name and ID from node metadata
#     assert rob["name"] == "robot"
#     assert rob["id"] == "r_1"
#     # Class should be actor
#     assert rob["class"] == "composite"

# def test_distance_sensor_detects_robot(node):
#     """Sonar should detect nearby robots within range."""
#     aff = node.handle_distance_sensor("so_1")
#     assert "r_1" in aff

#     rob = aff["r_1"]
#     # Check distance: sensor(17, 17) -> robot(8,13) = sqrt(9^2 + 4^2) = 9.85
#     assert rob["distance"] == pytest.approx(9,85, abs=1e-2)
#     # Name and ID from node metadata
#     assert rob["name"] == "robot"
#     assert rob["id"] == "r_1"
#     # Class should be actor
#     assert rob["class"] == "composite"
