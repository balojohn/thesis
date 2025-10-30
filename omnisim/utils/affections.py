import math, random
from omnisim.utils.utils import apply_noise
from omnisim.utils.geometry import (
    calc_distance,
    check_lines_intersection,
    get_shape_world_points,
)

def find_pose_by_metadata(poses_section, cls, type, subtype, name):
    """Recursively find a pose dict with x,y,theta by name inside poses tree."""
    if not isinstance(poses_section, dict):
        return None

    for key, val in poses_section.items():
        if key == name and isinstance(val, dict):
            if all(k in val for k in ("x", "y", "theta")):
                return val

        # Only recurse deeper if the value is a dict
        if isinstance(val, dict):
            found = find_pose_by_metadata(val, cls, type, subtype, name)
            if found:
                return found

    return None


def find_nodes_by_metadata(nodes_section, cls=None, type=None, subtype=None):
    """
    Recursively collect all node dicts from `nodes_section` matching metadata.
    Returns a list of node dicts.
    """
    found = []
    if not isinstance(nodes_section, dict):
        return found

    # Match level if this is a node dict with 'class'
    if "class" in nodes_section:
        c = nodes_section.get("class", "").lower()
        t = nodes_section.get("type", "").lower() or None
        st = nodes_section.get("subtype", "").lower() or None
        if ((cls is None or c == cls) and
            (type is None or t == type) and
            (subtype is None or st == subtype)):
            found.append(nodes_section)

    # Recurse into nested dicts
    for val in nodes_section.values():
        if isinstance(val, dict):
            found.extend(find_nodes_by_metadata(val, cls, type, subtype))
    return found

def find_node_by_id(nodes_section, node_id):
    try:
        if not isinstance(nodes_section, dict):
            return None
        for key, val in nodes_section.items():
            if isinstance(val, dict):
                if key == node_id or val.get("name") == node_id:
                    return val
                res = find_node_by_id(val, node_id)
                if res:
                    return res
        return None
    except Exception as e:
        print(f"[find_node_by_id ERROR] {e} in section keys={list(nodes_section.keys())}")
        return None

def handle_affection_ranged(nodes, poses, log, sensor: dict, node: dict, type):
    """
    Check if pose_start is within the range of node_id.
    """    
    # Sensor info
    sensor_class = sensor.get("class", "").lower()   # should be "sensor"
    sensor_type = sensor.get("type", "").lower() or None
    sensor_subtype = sensor.get("subtype", "").lower() or None
    sensor_name = sensor.get("name", "").lower()

    pose_start = find_pose_by_metadata(poses, sensor_class, sensor_type, sensor_subtype, sensor_name)
    if not pose_start:
        log.warning(f"[Affection] Pose not found for sensor {sensor_name}")
        return None

    # Target node info
    node_class = node.get("class", "").lower()              # e.g. "sensor", "actuator", "actor", "composite", "obstacle"
    node_type = node.get("type", "").lower() or None        # e.g. "envdevice", "envsensor", "envactor"
    node_subtype = node.get("subtype", "").lower() or None  # e.g. "thermostat", "temperature", "fire"
    node_name = node.get("name", "").lower()                # e.g. "th_1"

    pose_end = find_pose_by_metadata(poses, node_class, node_type, node_subtype, node_name)
    if not pose_end:
        log.warning(f"[Affection] Pose not found for target {node_name}")
        return None

    # Distance between sensor and target
    dist = calc_distance(
        [pose_start['x'], pose_start['y']],
        [pose_end['x'], pose_end['y']]
    )
    sensor_range = sensor.get("properties", {}).get("range", 0)
    
    if dist < sensor_range:  # within affection range
        result = {
            'class': node_class,
            'type': node_type,
            'subtype': node_subtype,
            'name': node_name,
            'distance': dist,
            'range': sensor_range,
        }
        # Merge node properties at top-level
        result.update(node.get('properties', {}))
        return result
    return None

def handle_affection_arced(nodes, poses, log, sensor, node, type,
                           sensor_pose=None, target_pose=None):
    """
    Handles the affection of an arced sensor (FOV-based detection).
    Now supports explicit sensor_pose / target_pose overrides.
    """
    try:
        # --- Sensor info ---
        sensor_class = sensor.get("class", "").lower()
        sensor_type = sensor.get("type", "").lower() or None
        sensor_subtype = sensor.get("subtype", "").lower() or None
        sensor_name = sensor.get("name", "").lower()

        # --- Get sensor pose (either passed or found) ---
        pose_start = sensor_pose or find_pose_by_metadata(
            poses, sensor_class, sensor_type, sensor_subtype, sensor_name
        )
        if not pose_start:
            log.warning(f"[Affection] Pose not found for arced sensor {sensor_name}")
            return None

        # --- Target info ---
        node_class = node.get("class", "").lower()
        node_type = node.get("type", "").lower() or None
        node_subtype = node.get("subtype", "").lower() or None
        node_name = node.get("name", "").lower()
        node_id = node.get("id", node_name)

        pose_end = target_pose or find_pose_by_metadata(
            poses, node_class, node_type, node_subtype, node_name
        )
        if not pose_end:
            log.warning(f"[Affection] Pose not found for target {node_name}")
            return None

        # --- Distance and FOV ---
        dist = calc_distance(
            [pose_start["x"], pose_start["y"]],
            [pose_end["x"], pose_end["y"]]
        )
        props = sensor.get("properties", {})
        sensor_range = props.get("range", sensor.get("range", 0))
        fov_deg = props.get("fov", sensor.get("fov", 0))
        fov_rad = math.radians(fov_deg)

        log.info(f"[Affection:Arced] {sensor_name} -> {node_name} | dist={dist:.2f}, range={sensor_range}, FOV={fov_deg}")

        if dist > sensor_range:
            return None

        # --- Compute angles ---
        theta_s = math.radians(pose_start["theta"])
        dx = pose_end["x"] - pose_start["x"]
        dy = pose_end["y"] - pose_start["y"]
        angle = math.atan2(dy, dx)

        def normalize_angle(a):
            return (a + math.pi) % (2 * math.pi) - math.pi

        min_a = normalize_angle(theta_s - fov_rad / 2)
        max_a = normalize_angle(theta_s + fov_rad / 2)
        angle_n = normalize_angle(angle)

        def in_fov(min_a, max_a, angle):
            if min_a <= max_a:
                return min_a <= angle <= max_a
            return angle >= min_a or angle <= max_a

        if not in_fov(min_a, max_a, angle_n):
            return None

        # --- Build result ---
        result = {
            "class": node_class,
            "type": node_type,
            "subtype": node_subtype,
            "name": node_name,
            "id": node_id,
            "distance": dist,
            "min_sensor_ang": min_a,
            "max_sensor_ang": max_a,
            "angle": angle_n,
            "range": sensor_range,
            "fov": fov_deg,
        }
        result.update(node.get("properties", {}))
        return result

    except Exception as e:
        log.error(f"handle_affection_arced: {e}")
        raise

def handle_temperature_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute the resulting temperature reading for an environmental sensor.
    Influences: thermostats (actuators.envdevice.thermostat) and fires (actors.envactor.fire).
    Returns: {"temperature": float}
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        props = sensor.get("properties", {})
        env_temp = (env_properties or {}).get("temperature", 25.0)
        influences = []
        noise = props.get("noise", 0.0)  # sensor-specific noise amplitude

        thermostats = find_nodes_by_metadata(nodes, cls="actuator", type="envdevice", subtype="thermostat")
        fires = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="fire")

        # --- Thermostat influences ---
        for target in thermostats:
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "temperature")
            if r:
                dist = r["distance"]
                rng = r["range"]
                weight = max(0.0, 1.0 - dist / rng)
                target_val = r.get("target_value", env_temp)
                influences.append(weight * target_val + (1 - weight) * env_temp)

        # --- Fire influences (increase temp strongly) ---
        for target in fires:
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "temperature")
            if r:
                dist = r["distance"]
                rng = r["range"]
                weight = max(0.0, 1.0 - dist / rng)
                val = r.get("value", env_temp)
                influences.append(weight * val + (1 - weight) * env_temp)

        # --- Compute final reading ---
        if influences:
            sensed_temp = sum(influences) / len(influences)
        else:
            sensed_temp = env_temp

        # Apply noise
        sensed_temp = apply_noise(sensed_temp, noise)

        return {"temperature": round(sensed_temp, 2)}

    except Exception as e:
        log.error(f"handle_temperature_sensor: {e}")
        raise


# Affected by humidifiers and waters
def handle_humidity_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Handles the humidity data for an environmental sensor.
    This method processes the humidity data for a given environmental sensor by 
    checking the influence of humifiers and waters on the sensor's location.
    Args:
        name (str): The name of the environmental sensor.
    Returns:
        dict: A dictionary containing the humidity data influenced by humifiers 
                and waters, keyed by the influencing factor.
    Raises:
        Exception: If an error occurs during the processing, it logs the error and 
                    raises an exception with the error message.
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        props = sensor.get("properties", {})
        env_hum = (env_properties or {}).get("humidity", 40.0)
        influences = []
        noise = props.get("noise", 0.0)  # sensor-specific noise amplitude

        humidifiers = find_nodes_by_metadata(nodes, cls="actuator", type="envdevice", subtype="humidifier")
        waters = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="water")

        # Humidifier influences
        for target in humidifiers:
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "humidity")
            if r:
                dist = r["distance"]
                rng = r["range"]
                weight = max(0.0, 1.0 - dist / rng)
                target_val = r.get("target_value", env_hum)
                influences.append(weight * target_val + (1 - weight) * env_hum)

        # Water influences
        for target in waters:
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "temperature")
            if r:
                dist = r["distance"]
                rng = r["range"]
                weight = max(0.0, 1.0 - dist / rng)
                val = r.get("value", env_hum)
                influences.append(weight * val + (1 - weight) * env_hum)

        # Compute final reading
        if influences:
            sensed_hum = sum(influences) / len(influences)
        else:
            sensed_hum = env_hum

        # Apply noise
        sensed_hum = apply_noise(sensed_hum, noise)

        return {"humidity": round(sensed_hum, 2)}
    
    except Exception as e:
        log.error(f"handle_humidity_sensor: {e}")
        raise

# Affected by humans and fires
def handle_gas_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute gas concentration for an environmental sensor.
    Influences:
      - Humans (CO₂ emission)
      - Fires (smoke emission, derived from fire.value)
    Returns: {"gas": float}
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        props = sensor.get("properties", {})
        env_gas = (env_properties or {}).get("gas", 0.0)
        influences = []
        noise = props.get("noise", 0.0)

        humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
        fires = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="fire")

        for target in humans + fires:
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "gas")
            log.info(f"[GasCheck] {sensor_id} -> {target['name']}, result={r}")
            if not r:
                continue

            dist = r["distance"]
            rng = r["range"]
            weight = max(0.0, 1.0 - dist / rng)

            if target["subtype"] == "fire":
                # --- Smoke intensity derived from heat value ---
                fire_val = target.get("properties", {}).get("value", 0.0)
                smoke_factor = 0.3   # 30 % of fire intensity becomes smoke
                target_val = fire_val * smoke_factor
            elif target["subtype"] == "human":
                # Human CO₂ emission (can come from r["value"] or fixed)
                target_val = r.get("value", env_gas + 5.0)
            else:
                target_val = env_gas

            influences.append(weight * target_val + (1 - weight) * env_gas)

        sensed_gas = sum(influences) / len(influences) if influences else env_gas
        sensed_gas = apply_noise(sensed_gas, noise)
        return {"gas": round(sensed_gas, 2)}

    except Exception as e:
        log.error(f"handle_gas_sensor: {e}")
        raise

# Affected by humans with sound, sound sources, speakers (when playing smth),
# robots (when moving)
def handle_microphone_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute perceived sound level at a microphone.
    Influences: humans (speaking), sound sources, speakers.
    Returns: {"sound": float}
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        props = sensor.get("properties", {})
        env_sound = (env_properties or {}).get("sound", 20.0)
        influences = []
        noise = props.get("noise", 0.0)
        mic_range = props.get("range", sensor.get("range", 0))  # new

        speakers = find_nodes_by_metadata(nodes, cls="actuator", subtype="speaker")
        humans = find_nodes_by_metadata(nodes, cls="actor", type="human")
        soundsources = find_nodes_by_metadata(nodes, cls="actor", type="soundsource")

        log.info(f"[Microphone] Evaluating {sensor_id} at env_sound={env_sound}")
        for target in speakers + humans + soundsources:
            tname = target.get("name", "unknown")
            props_t = target.get("properties", {})
            src_sound = props_t.get("sound", target.get("sound", env_sound))
            src_range = props_t.get("range", target.get("range", 0))
            if src_sound == 0:
                continue

            r = handle_affection_ranged(nodes, poses, log, sensor, target, "sound")
            if not r:
                log.debug(f"    [skip] {tname}: out of range or not visible")
                continue

            dist = r["distance"]

            # --- FIX: use the *larger* of source/sensor ranges ---
            rng = max(src_range, mic_range, r.get("range", 0))
            if rng <= 0:
                log.debug(f"    [skip] {tname}: invalid range {rng}")
                continue

            weight = max(0.0, 1.0 - dist / rng)
            sensed_val = weight * src_sound + (1 - weight) * env_sound

            if weight > 0.0:
                influences.append(sensed_val)
                log.info(f"    [src] {tname}: sound={src_sound}, dist={dist:.1f}, "
                         f"range={rng}, weight={weight:.3f}, contrib={sensed_val:.2f}")
            else:
                log.debug(f"    [skip] {tname}: out of range ({dist:.1f}>{rng})")

        # --- Combine all contributions ---
        if influences:
            sensed_sound = max(env_sound, sum(influences) / len(influences))
            log.info(f"    [mix] Averaged {len(influences)} influences -> {sensed_sound:.2f}")
        else:
            sensed_sound = env_sound
            log.info(f"    [mix] No influences -> baseline {sensed_sound:.2f}")

        # --- Add noise ---
        sensed_sound = apply_noise(sensed_sound, noise)
        log.info(f"    [final] After noise ({noise}) -> {sensed_sound:.2f}")

        return {"sound": round(sensed_sound, 2)}

    except Exception as e:
        log.error(f"handle_microphone_sensor: {e}")
        raise


def compute_luminosity(nodes, poses, log, sensor_id, env_properties=None, print_debug=False):
    """
    Compute the luminosity at a given place identified by `name`.
    This method calculates the luminosity at a specific location by considering
    the contributions from environmental light sources, robot LEDs, and actor fires.
    It also factors in the environmental luminosity and ensures the final luminosity
    value is within the range [0, 100]. Optionally, it can print debug information
    during the computation process.
    Args:
        name (str): The name of the place for which to compute the luminosity.
        print_debug (bool, optional): If True, prints debug information. Defaults to False.
    Returns:
        float: The computed luminosity value, with a small random variation added.
    """
    try:
        # --- Initialization ---
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            raise Exception(f"[Luminosity] Sensor '{sensor_id}' not found in nodes")
        env_luminosity = (env_properties or {}).get("luminosity", 60.0)
        lum = 0.0
        noise = sensor.get("properties", {}).get("noise", 0.0)

        # --- Find sensor pose ---
        pose = find_pose_by_metadata(
            poses,
            cls=sensor.get("class", "").lower(),
            type=sensor.get("type", "").lower(),
            subtype=sensor.get("subtype", "").lower(),
            name=sensor.get("name", "").lower()
        )
        if not pose:
            log.warning(f"[Luminosity] Pose not found for {sensor_id}")
            return env_luminosity

        sensor_pose = [pose["x"], pose["y"]]
        if print_debug:
            log.info(f"[Luminosity] Computing for {sensor_id} at {sensor_pose}")

        # --- (1) Environmental lights (LEDs) ---
        leds = find_nodes_by_metadata(nodes, cls="actuator", type="singleled", subtype="led")
        for led in leds:
            r = handle_affection_ranged(nodes, poses, log, sensor, led, "light")
            if r:
                dist = r["distance"]
                rng = r["range"]
                weight = max(0.0, 1.0 - dist / rng)
                led_val = r.get("value", 100.0)
                lum += weight * led_val
                if print_debug:
                    log.info(f"\t[LED] {led['name']} @dist {dist:.1f} contributes {weight * led_val:.1f}")
                    src = led.get("parent", {}).get("name", "environment")
                    log.info(f"\t[LED] {led['name']} from {src} -> +{weight * led_val:.1f}")

        # --- (2) Fire actors ---
        fires = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="fire")
        for fire in fires:
            r = handle_affection_ranged(nodes, poses, log, sensor, fire, "light")
            if r:
                dist = r["distance"]
                rng = r["range"]
                weight = max(0.0, 1.0 - dist / rng)
                fire_val = r.get("value", 100.0)
                lum += weight * fire_val
                if print_debug:
                    log.info(f"\t[Fire] {fire['name']} @dist {dist:.1f} contributes {weight * fire_val:.1f}")

        # (3) Blend with environmental baseline
        if lum < env_luminosity:
            lum = lum * 0.1 + env_luminosity
        else:
            lum = env_luminosity * 0.1 + lum
        # Clamp and add noise
        lum = max(0.0, min(100.0, lum))
        lum = apply_noise(lum, noise)
        lum += random.uniform(-0.25, 0.25)

        if print_debug:
            log.info(f"\t[Final Luminosity] {lum:.2f} (env={env_luminosity})")

        return round(lum, 2)
    except Exception as e:
        log.error(f"compute_luminosity: {e}")
        raise

# Affected by light, fire
# Affected by fire (intensity based on its value)
def handle_light_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute perceived light intensity at a sensor.
    Influences: fires only (intensity derived from fire.value)
    Returns: {"light": float}
    """
    try:
        log.info(f"[LightSensor] Evaluating {sensor_id}")

        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            log.warning(f"[LightSensor] Sensor {sensor_id} not found in node tree!")
            return {"light": (env_properties or {}).get("luminosity", 60.0)}

        props = sensor.get("properties", {})
        env_light = (env_properties or {}).get("luminosity", 60.0)
        influences = []
        noise = props.get("noise", 0.0)

        log.info(f"[LightSensor] Baseline env_luminosity={env_light}, noise={noise}")

        # --- Collect all light sources: fires + LEDs ---
        fires = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="fire")
        leds = find_nodes_by_metadata(nodes, cls="actuator", type="singleled", subtype="led")
        sources = fires + leds
        log.info(f"[LightSensor] Found {len(sources)} light source(s): {[s.get('name') for s in sources]}")

        # --- Evaluate each fire influence ---
        for target in sources:
            fname = target.get("name", "unknown")
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "light")
            if not r:
                log.info(f"    [skip] {fname}: out of range or pose not found")
                continue

            dist = r["distance"]
            rng = r["range"]
            weight = max(0.0, 1.0 - dist / rng)

            if target["subtype"] == "fire":
                # --- Smoke intensity derived from heat value ---
                fire_val = target.get("properties", {}).get("value", 0.0)
                luminosity_factor = 0.3   # 30 % of fire intensity becomes luminosity
                target_val = fire_val * luminosity_factor
            elif target["subtype"] == "led":
                color_hex = target.get("properties", {}).get("color", "#FFFFFF")
                # Convert hex → RGB [0..1]
                r = int(color_hex[1:3], 16) / 255.0
                g = int(color_hex[3:5], 16) / 255.0
                b = int(color_hex[5:7], 16) / 255.0
                # Compute luminance (perceived brightness)
                luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
                # Scale to 0–100 range
                target_val = luminance * 100.0
            else:
                target_val = env_light
            
            influences.append(weight * target_val)
            log.info(
                f"    [fire] {fname}: value={fire_val}, dist={dist:.1f}, "
                f"range={rng}, weight={weight:.3f}, contrib={target_val:.2f}"
            )

        # --- Combine influences ---
        if influences:
            # Absolute addition (without clamping to 0-100)
            sensed_light = env_light + sum(influences)
            log.info(f"[LightSensor] Combined {len(influences)} influence(s) -> {sensed_light:.2f}")
        else:
            sensed_light = env_light
            log.info(f"[LightSensor] No fires in range -> using baseline {sensed_light:.2f}")

        # sensed_light = max(0.0, min(100.0, sensed_light))
        # --- Apply noise ---
        # sensed_light = apply_noise(sensed_light, noise)
        log.info(f"[LightSensor] Final (after noise) -> {sensed_light:.2f}")

        return {"light": round(sensed_light, 2)}

    except Exception as e:
        log.error(f"handle_light_sensor: {e}")
        raise

# Affected by robots
def handle_distance_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute distance readings for robots in range.
    Returns: {"distance": float} of the nearest detected robot.
    """
    try:
        # --- Find the sensor node (recursively) ---
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            log.warning(f"[Sonar] Sensor {sensor_id} not found in node tree.")
            return {"distance": 0.0}
        
        props = sensor.get("properties", {})
        noise = props.get("noise", 0.0)

        # --- Find sensor pose recursively ---
        sensor_pose = find_pose_by_metadata(
            poses,
            sensor.get("class", ""),
            sensor.get("type", ""),
            sensor.get("subtype", ""),
            sensor.get("name", "")
        )
        if not sensor_pose:
            log.warning(f"[Sonar] Pose for {sensor_id} not found in pose tree.")
            return {"distance": 0.0}

        # --- Collect potential targets ---
        robots = find_nodes_by_metadata(nodes, cls="composite", type="robot")
        obstacles = find_nodes_by_metadata(nodes, cls="obstacle")
        actors = find_nodes_by_metadata(nodes, cls="actor")  # optional (fires, humans, etc.)
        potential_targets = robots + obstacles + actors

        min_dist = None
        nearest_obj = None

        for target in potential_targets:
            if target.get("name") == sensor.get("name"):
                continue

            # --- Compute target pose recursively ---
            target_pose = find_pose_by_metadata(
                poses,
                target.get("class", ""),
                target.get("type", ""),
                target.get("subtype", ""),
                target.get("name", "")
            )
            if not target_pose:
                continue

            # --- Perform distance + FOV intersection check ---
            r = handle_affection_arced(
                nodes, poses, log,
                sensor, target, target.get("subtype"),
                sensor_pose=sensor_pose, target_pose=target_pose
            )

            if r:
                d = r["distance"]
                if min_dist is None or d < min_dist:
                    min_dist = d
                    nearest_obj = r

        # --- Fallback: nothing detected ---
        if min_dist is None:
            sensed_dist = props.get("range", 0)
            return {
                "distance": round(apply_noise(sensed_dist, noise), 2),
                "detected_class": None,
                "detected_type": None,
                "detected_subtype": None,
                "detected_name": None,
            }

        # --- Return detection result ---
        sensed_dist = apply_noise(min_dist, noise)
        return {
            "distance": round(sensed_dist, 2),
            "detected_class": nearest_obj.get("class"),
            "detected_type": nearest_obj.get("type"),
            "detected_subtype": nearest_obj.get("subtype"),
            "detected_name": nearest_obj.get("name"),
        }

    except Exception as e:
        import traceback
        log.error(f"handle_distance_sensor({sensor_id}) crashed: {e}\n{traceback.format_exc()}")
        raise

# Affected by barcode, color, human, qr, text
def handle_camera_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Processes sensor data from a camera and handles different types of actors 
    (human, qr, barcode, color, text) and optionally robots.
    Args:
        name (str): The name of the place or sensor.
        with_robots (bool, optional): If True, includes robots in the processing. 
        Defaults to False.
    Returns:
        dict: A dictionary containing the detected actors and their respective processed data.
    Raises:
        Exception: If an error occurs during processing.
    The function performs the following steps:
    1. Retrieves the absolute place data for the given name.
    2. Computes the luminosity of the place.
    3. Processes different types of actors (human, qr, barcode, color, text) and stores the 
        results.
    4. Optionally processes robots if `with_robots` is True.
    5. Filters the results based on the luminosity, simulating detection failure in low light 
        conditions.
    6. Logs and raises an exception if any error occurs during processing.
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            # Fallback: search within composites manually
            sensors = find_nodes_by_metadata(nodes, cls="sensor", subtype="camera")
            for s in sensors:
                if s.get("name") == sensor_id:
                    sensor = s
                    break
                
        if not sensor:
            log.warning(f"[Camera] Sensor {sensor_id} not found in node tree.")
            return {}
        props = sensor.get("properties", {})
        detections = {}
        noise = props.get("noise", 0.0)

        # (1) Retrieve pose
        pose = find_pose_by_metadata(
            poses,
            cls=sensor.get("class", "").lower(),
            type=sensor.get("type", "").lower(),
            subtype=sensor.get("subtype", "").lower(),
            name=sensor.get("name", "").lower()
        )
        if not pose:
            log.warning(f"[Camera] Pose not found for {sensor_id}")
            return {}
        
        # (2) Compute luminosity
        luminosity = compute_luminosity(nodes, poses, log, sensor_id, env_properties)
        log.info(f"[Camera] {sensor_id}: local luminosity = {round(luminosity, 2)}")

        # (3) Gather visible target types ==
        humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
        qrs = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="qrcode")
        barcodes = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="barcode")
        texts = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="plaintext")
        colors = find_nodes_by_metadata(nodes, cls="actor", subtype="color")
        leds = find_nodes_by_metadata(nodes, cls="actuator", type="singleled", subtype="led")
        robots = find_nodes_by_metadata(nodes, cls="composite", type="robot")

        visible_targets = humans + qrs + barcodes + texts + colors + leds + robots

        # (4) Check visibility (FOV/range detection)
        for target in visible_targets:
            handler = handle_affection_arced if target["class"] != "actuator" else handle_affection_ranged
            r = handler(nodes, poses, log, sensor, target, target.get("subtype"))
            if r:
                detections[target["name"]] = {
                    "class": r["class"],
                    "type": r["type"],
                    "subtype": r["subtype"],
                    "distance": round(apply_noise(r["distance"], noise), 2),
                    "angle": round(math.degrees(r.get("angle", 0.0)), 2) if "angle" in r else None,
                    "fov": r.get("fov", None),
                    "visible": True,
                }
        
        # (5) Filter based on luminosity
        # If light < 30, randomly drop detections to simulate low-light failure
        if luminosity < 30 and detections:
            fail_prob = (30 - luminosity) / 30.0  # 0 → 1 range
            dropped = [
                k for k in list(detections.keys()) if random.random() < fail_prob
            ]
            for k in dropped:
                detections.pop(k, None)
            if dropped:
                log.info(f"[Camera] {sensor_id}: low light ({luminosity:.1f}) -> lost {len(dropped)} detections")

        return detections
    
    except Exception as e:
        log.error(f"handle_camera_sensor: {e}")
        raise
    
# Affected by rfid_tags
def handle_rfid_sensor(nodes, poses, log, sensor_id):
    """
    Detect RFID tags within range/FOV of the RFID reader.
    Returns:
        dict of detections: {tag_name: {distance, signal_strength, ...}}
    """
    try:
        sensor = nodes[sensor_id]
        detections = {}

        tags = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="rfidtag")

        for target in tags:
            r = handle_affection_arced(nodes, poses, log, sensor, target, "rfid_tag")
            if r:
                dist = r["distance"]
                rng = r["range"]
                weight = max(0.0, 1.0 - dist / rng)
                signal = round(weight * 100.0, 2)  # signal strength percentage
                detections[target["name"]] = {
                    "distance": dist,
                    "signal_strength": signal,
                    "range": rng,
                    "class": r["class"],
                    "type": r["type"],
                    "subtype": r["subtype"],
                }

        return detections

    except Exception as e:
        log.error(f"handle_rfid_sensor: {e}")
        raise

# Affected by robots
def handle_area_alarm(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute area alarm trigger based on proximity of robots.
    Influences: robots (composite.type=robot)
    Returns: {"triggered": bool, "detections": {robot_id: {"distance": float, "range": float}}}
    """
    try:
        log.info(f"[AreaAlarm] Evaluating {sensor_id}")

        # --- Locate the alarm sensor node ---
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            log.warning(f"[AreaAlarm] Sensor {sensor_id} not found in node tree.")
            return {"triggered": False, "detections": {}}

        props = sensor.get("properties", {})
        sensor_range = props.get("range", 100.0)
        noise = props.get("noise", 0.0)

        # --- Find the alarm’s pose ---
        sensor_pose = find_pose_by_metadata(
            poses,
            cls=sensor.get("class", "").lower(),
            type=sensor.get("type", "").lower(),
            subtype=sensor.get("subtype", "").lower(),
            name=sensor.get("name", "").lower()
        )
        if not sensor_pose:
            log.warning(f"[AreaAlarm] Pose not found for {sensor_id}")
            return {"triggered": False, "detections": {}}

        # --- Collect all robots ---
        robots = find_nodes_by_metadata(nodes, cls="composite", type="robot")
        detections = {}
        triggered = False

        # --- Check each robot ---
        for target in robots:
            rid = target.get("name")
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "robot")
            if not r:
                continue
            
            if not r or "distance" not in r or r["distance"] is None:
                log.debug(f"[AreaAlarm][DEBUG] Skipping {rid}: no valid distance {r}")
                continue
            dist = r["distance"]
            rng = r["range"]
            weight = max(0.0, 1.0 - dist / rng)

            # Store detection details
            detections[rid] = {
                "distance": round(apply_noise(dist, noise), 2),
                "range": rng,
                "weight": round(weight, 3)
            }

            if dist <= rng:
                triggered = True
                log.info(f"[AreaAlarm] Triggered by {rid} at {dist:.1f}/{rng:.1f}")

        # --- Result ---
        result = {
            "triggered": True if triggered else False,
            "detections": ", ".join(detections.keys()) if detections else "{}"
        }
        log.info(f"[AreaAlarm] Result for {sensor_id}: {result}")
        return result

    except Exception as e:
        import traceback
        log.error(f"handle_area_alarm({sensor_id}) crashed: {e}\n{traceback.format_exc()}")
        return {"triggered": False, "detections": "{}"}

# Affected by robots
def handle_linear_alarm(nodes, poses, log, sensor_id):
    """
    Handles linear alarms for robots based on their positions and declared linear paths.
    Args:
        name (str): The name of the linear declaration to check against.
    Returns:
        dict: A dictionary where keys are robot identifiers and values are True if an 
        intersection with the linear path is detected.
    Raises:
        Exception: If any error occurs during the processing, it logs the error and raises 
        an Exception.
    This method performs the following steps:
    1. Retrieves the start and end positions of the linear declaration.
    2. Calculates the distance between the start and end positions.
    3. Iterates through all robots to check if their current path intersects with the linear 
        declaration.
    4. Updates the robot's previous and current positions.
    5. Checks for intersections between the robot's path and the linear declaration.
    6. Logs and raises any exceptions encountered during processing.
    """
    try:
        log.info(f"[LinearAlarm] Evaluating {sensor_id}")

        # --- Locate the alarm sensor node ---
        sensor = find_node_by_id(nodes, sensor_id)
        if not isinstance(sensor, dict):
            log.warning(f"[LinearAlarm] Sensor {sensor_id} not found or invalid")
            return {"triggered": False, "detections": {}}

        shape = sensor.get("shape")
        if not shape or not isinstance(shape, dict):
            log.warning(f"[LinearAlarm] Sensor {sensor_id} has no valid shape! shape={shape}")
            return {"triggered": False, "detections": {}}

        points = shape.get("points")
        if not points or len(points) < 2:
            log.warning(f"[LinearAlarm] Sensor {sensor_id} shape has insufficient points!")
            return {"triggered": False, "detections": {}}

        # --- Retrieve pose ---
        pose = find_pose_by_metadata(
            poses,
            cls=sensor.get("class", "").lower(),
            type=sensor.get("type", "").lower(),
            subtype=sensor.get("subtype", "").lower(),
            name=sensor.get("name", "").lower(),
        )
        if not pose:
            log.warning(f"[LinearAlarm] Pose not found for {sensor_id}")
            return {"triggered": False, "detections": {}}

        ent_x, ent_y, ent_theta = pose["x"], pose["y"], pose["theta"]
        rot = math.radians(ent_theta)

        # --- Beam endpoints in world coordinates ---
        start = [
            ent_x + (points[0]["x"] * math.cos(rot) - points[0]["y"] * math.sin(rot)),
            ent_y + (points[0]["x"] * math.sin(rot) + points[0]["y"] * math.cos(rot))
        ]
        end = [
            ent_x + (points[1]["x"] * math.cos(rot) - points[1]["y"] * math.sin(rot)),
            ent_y + (points[1]["x"] * math.sin(rot) + points[1]["y"] * math.cos(rot))
        ]

        # --- Gather robots ---
        robots = find_nodes_by_metadata(nodes, cls="composite", type="robot")
        detections = []
        triggered = False

        log.info(f"[LinearAlarm][DEBUG] Beam start={start}, end={end}")
        for robot in robots:
            rname = robot.get("name")
            robot_pose = find_pose_by_metadata(poses, "composite", "robot", None, rname)
            if not robot_pose:
                continue

            shape_r = robot.get("shape", {})
            if not shape_r:
                continue
            # === Compute world-space corners using your visualizer logic ===
            # (this helper produces the same points visualized on screen)
            world_pts = get_shape_world_points(robot_pose, shape_r)

            if not world_pts or len(world_pts) < 2:
                continue

            log.info(f"[LinearAlarm][DEBUG] Robot {rname} pose={robot_pose}")
            log.info(f"[LinearAlarm][DEBUG] Robot {rname} world_pts={world_pts}")

            # --- Build robot edges from its perimeter ---
            edges = list(zip(world_pts, world_pts[1:] + [world_pts[0]]))

            # --- Check intersection between beam and robot edges ---
            for edge_start, edge_end in edges:
                if check_lines_intersection(start, end, edge_start, edge_end):
                    triggered = True
                    detections.append(rname)
                    log.info(f"[LinearAlarm] Robot {rname} intersects beam {sensor_id}")
                    break

        result = {
            "triggered": True if triggered else False,
            "detections": ", ".join(detections) if detections else "{}"
        }
        log.info(f"[LinearAlarm] Result for {sensor_id}: {result}")
        return result

    except Exception as e:
        import traceback
        log.error(f"handle_linear_alarm({sensor_id}) crashed: {e}\n{traceback.format_exc()}")
        return {"triggered": False, "detections": {}}

def check_affectability(nodes, poses, log, sensor_id, env_properties):
    """
    Check the affectability of a device based on its type and subtype.
    Parameters:
    name (str): The name of the device to check.
    Returns:
    dict: A dictionary containing the results of the affectability check.
    Raises:
    Exception: If the device name is not found in declarations_info or if there is an 
    error in device handling.
    """
    # --- Try to resolve node dict ---
    sensor = None
    if sensor_id in nodes:
        sensor = nodes[sensor_id]
    else:
        # fallback recursive search for nested sensors
        all_sensors = find_nodes_by_metadata(nodes, cls="sensor")
        for s in all_sensors:
            if s.get("name") == sensor_id:
                sensor = s
                break

    if not sensor:
        raise Exception(f"[Affectability] Sensor '{sensor_id}' not found in nodes structure")

    node_class = sensor.get("class", "").lower()
    node_type = (sensor.get("type") or "").lower() or None
    node_subtype = (sensor.get("subtype") or "").lower() or None
    node_name = (sensor.get("name") or "").lower()

    log.info(f"[Affectability] Evaluating {node_class}:{node_type}:{node_subtype or ''} -> {node_name}")

    affected = {}
    try:
        # --- Sensor-based affectability ---
        if node_class == "sensor":
            subtype = node_subtype or node_type

            if subtype == "temperature":
                affected = handle_temperature_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "humidity":
                affected = handle_humidity_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "gas":
                affected = handle_gas_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "microphone":
                affected = handle_microphone_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "camera":
                affected = handle_camera_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "rfid":
                affected = handle_rfid_sensor(nodes, poses, log, sensor_id)
            elif subtype == "areaalarm":
                affected = handle_area_alarm(nodes, poses, log, sensor_id)
            elif subtype == "linearalarm":
                affected = handle_linear_alarm(nodes, poses, log, sensor_id)
            elif subtype in ("sonar", "ir"):
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif subtype == "light":
                affected = handle_light_sensor(nodes, poses, log, sensor_id, env_properties)

        # --- Composite sensors (robot-mounted sensors, pantilt, etc.) ---
        elif node_class == "composite" and node_type == "robot":
            subtype = node_subtype or node_name

            if subtype == "microphone":
                affected = handle_microphone_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "camera":
                affected = handle_camera_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "rfid":
                affected = handle_rfid_sensor(nodes, poses, log, sensor_id)
            elif subtype in ("sonar", "ir"):
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif subtype == "temperature":
                affected = handle_temperature_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "humidity":
                affected = handle_humidity_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "gas":
                affected = handle_gas_sensor(nodes, poses, log, sensor_id, env_properties)

        # --- Optional: pure actuator or actor cases could go here in future ---

    except Exception as e:
        log.error(f"[Affectability] Error handling {sensor_id}: {e}")
        raise

    return {
        "affections": affected,
        "env_properties": env_properties
    }
