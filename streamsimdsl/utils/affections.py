import math, random
from streamsimdsl.utils.utils import apply_noise, apply_dispersion
from streamsimdsl.utils.geometry import (
    calc_distance,
    check_lines_intersection,
    get_shape_world_points,
)

def find_pose_by_metadata(poses_section, cls, type, subtype, name):
    """Recursively find and normalize a pose dict with x,y,theta."""
    if not isinstance(poses_section, dict):
        return None

    name_l = name.lower()
    found_pose = None

    for key, val in poses_section.items():
        if isinstance(key, str) and key.lower() == name_l and isinstance(val, dict):
            # Case 1: absolute pose
            if all(k in val for k in ("x", "y", "theta")):
                return {"x": val["x"], "y": val["y"], "theta": val["theta"]}

            # Case 2: relative pose
            if "rel_pose" in val and all(k in val["rel_pose"] for k in ("x", "y", "theta")):
                rel = val["rel_pose"]
                return {"x": rel["x"], "y": rel["y"], "theta": rel["theta"]}

        if isinstance(val, dict):
            candidate = find_pose_by_metadata(val, cls, type, subtype, name)
            if candidate:
                found_pose = candidate

    return found_pose

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

def handle_affection_ranged(nodes, poses, log, sensor: dict, node: dict, type, dispersion=None):
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
    dist = calc_distance([pose_start['x'], pose_start['y']], [pose_end['x'], pose_end['y']])
    rng = node.get("properties", {}).get("range", 0.0)
    if rng <= 0 or dist > rng:
        return None

    weight = max(0.0, 1.0 - dist / rng)
    
    # disp = node.get("properties", {}).get("dispersion")
    if dispersion:
        dtype  = dispersion.get("type")
        params = {k:v for k,v in dispersion.items() if k != "type"}
        progress = apply_dispersion(weight, dtype, **params)
    else:
        progress = weight

    progress = max(0.0, min(1.0, progress))

    return {
        'class': node_class,
        'type': node_type,
        'subtype': node_subtype,
        'name': node_name,
        'distance': dist,
        'range': rng,
        'progress': progress,
        'dist_weight': weight,
    }
    # # Merge node properties at top-level
    # result.update(node.get('properties', {}))
    # return result

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

        # log.info(f"[Affection:Arced] {sensor_name} -> {node_name} | dist={dist:.2f}, range={sensor_range}, FOV={fov_deg}")

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

def affects(entity, property: str) -> bool:
    """
    Checks whether a node has an AffectEntry with id == substance.
    Works for both dict-based and TextX-object-based entries.
    """
    aff_list = entity.get("properties", {}).get("affects") or []
    prop = property.lower()

    for a in aff_list:
        # Extract id safely from dict or TextX object
        aid = a.get("id") if isinstance(a, dict) else getattr(a, "id", None)
        if aid and aid.lower() == prop:
            return True

    return False

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
        noise = props.get("noise", 0.0)  # sensor-specific noise amplitude
        influences = []
        
        thermostats = find_nodes_by_metadata(nodes, cls="actuator", type="envdevice", subtype="thermostat")
        fires = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="fire")
        custom_entities = [
            e for e in find_nodes_by_metadata(nodes)
            if affects(e, "temperature")
        ]

        # # collect influencers
        # for source in thermostats + fires + generic_entities:
        #     # skip entity unless it explicitly affects temperature
        #     if source in generic_entities and not affects(source, "temperature"):
        #         continue
            
        #     disp = None
        #     for a in source.get("properties", {}).get("affects", []):
        #         if a["id"].lower() == "temperature":
        #             disp = a.get("dispersion")
        #             target_val = a.get("target_value")
        #             break
            
        #     # fallback
        #     if target_val is None:
        #         target_val = source.get("properties", {}).get("value", env_temp)

        #     r = handle_affection_ranged(nodes, poses, log, sensor, source, "temperature", disp)
        #     if not r:
        #         continue
        #     progress = r["progress"]

        #     # influence relative to env_temp
        #     influence = progress * (target_val - env_temp)
        #     influences.append(influence)

        for source in thermostats + fires + custom_entities:
            disp = None
            target_val = None
            if affects(source, "temperature"):
                for a in source.get("properties", {}).get("affects", []):
                    if a["id"].lower() == "temperature":
                        disp = a.get("dispersion")
                        target_val = a.get("target_value")
                        break

                if target_val is None:
                    target_val = source.get("properties", {}).get("value", env_temp)

            else:
                disp = source.get("properties", {}).get("dispersion")
                target_val = source.get("properties", {}).get("value", env_temp)

            r = handle_affection_ranged(nodes, poses, log, sensor, source, "temperature", disp)
            if not r:
                continue

            progress = r["progress"]
            influence = progress * (target_val - env_temp)
            influences.append(influence)

        final = env_temp + sum(influences)
        # final = apply_noise(final, noise)
        final = round(final, 2)

        return {"temperature": final}

    except Exception as e:
        log.error(f"handle_temperature_sensor: {e}")
        raise

# Affected by humidifiers and waters
def handle_humidity_sensor(nodes, poses, log, sensor_id, env_properties=None):
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        props = sensor.get("properties", {})
        env_hum = (env_properties or {}).get("humidity", 40.0)
        noise = props.get("noise", 0.0)
        influences = []

        humidifiers = find_nodes_by_metadata(nodes, cls="actuator", type="envdevice", subtype="humidifier")
        waters = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="water")
        generic_entities = find_nodes_by_metadata(nodes)

        # collect influencers
        for source in humidifiers + waters + generic_entities:
            # skip entity unless it explicitly affects humidity
            if source in generic_entities and not affects(source, "humidity"):
                continue
            
            disp = None
            for a in source.get("properties", {}).get("affects", []):
                if a["id"].lower() == "humidity":
                    disp = a.get("dispersion")
                    target_val = a.get("target_value")
                    break
            
            # fallback
            if target_val is None:
                target_val = source.get("properties", {}).get("value", env_hum)

            r = handle_affection_ranged(nodes, poses, log, sensor, source, "humidity", disp)
            if not r:
                continue
            progress = r["progress"]

            # influence relative to env_hum
            influence = progress * (target_val - env_hum)
            influences.append(influence)
            
        final = env_hum + sum(influences)
        # final = apply_noise(final, noise)
        final = round(final, 2)
        
        return {"humidity": final}

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
        noise = props.get("noise", 0.0)
        influences = []

        # humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
        fires = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="fire")
        generic_entities = find_nodes_by_metadata(nodes)

        for source in fires + generic_entities:
            # skip entity unless it explicitly affects temperature
            if source in generic_entities and not affects(source, "gas"):
                continue

            disp = None
            for a in source.get("properties", {}).get("affects", []):
                if a["id"].lower() == "gas":
                    disp = a.get("dispersion")
                    target_val = a.get("target_value")
                    break
            
            # fallback
            if target_val is None:
                target_val = source.get("properties", {}).get("value", env_gas)

            r = handle_affection_ranged(nodes, poses, log, sensor, source, "gas", disp)
            if not r:
                continue
            progress = r["progress"]

            # influence relative to env_hum
            influence = progress * (target_val - env_gas)
            influences.append(influence)
            
        final = env_gas + sum(influences)
        # final = apply_noise(final, noise)
        final = round(final, 2)
        
        return {"gas": final}
    except Exception as e:
        log.error(f"handle_gas_sensor: {e}")
        raise

# Affected by fires, leds
def handle_light_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute perceived light intensity at a sensor.
    Influences: fires only (intensity derived from fire.value)
    Returns: {"light": float}
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        props = sensor.get("properties", {})
        env_light = (env_properties or {}).get("luminosity", 60.0)
        noise = props.get("noise", 0.0)
        influences = []

        fires = find_nodes_by_metadata(nodes, cls="actor", type="envactor", subtype="fire")
        leds = find_nodes_by_metadata(nodes, cls="actuator", type="singleled", subtype="led")
        generic_entities = find_nodes_by_metadata(nodes)
        
        for source in fires + leds + generic_entities:
            # skip entity unless it explicitly affects temperature
            if source in generic_entities and not affects(source, "light"):
                continue

            disp = None
            for a in source.get("properties", {}).get("affects", []):
                if a["id"].lower() == "light":
                    disp = a.get("dispersion")
                    target_val = a.get("target_value")
                    break
            
            # fallback
            if target_val is None:
                target_val = source.get("properties", {}).get("value", env_light)

            r = handle_affection_ranged(nodes, poses, log, sensor, source, "light", disp)
            if not r:
                continue
            progress = r["progress"]

            # influence relative to env_hum
            influence = progress * (target_val - env_light)
            influences.append(influence)
            
        final = env_light + sum(influences)
        # final = apply_noise(final, noise)
        final = round(final, 2)
        
        return {"light": final}

    except Exception as e:
        log.error(f"handle_light_sensor: {e}")
        raise

# Affected by humans with sound, sound sources, speakers (when playing smth),
# robots (when moving)
def handle_microphone_sensor(nodes, poses, log, sensor_id, env_properties=None, env=None):
    """
    Detects sound-emitting entities (humans, speakers, sound sources, robots).
    Returns a dict of detections {target_name: {...}} with distance and signal strength.
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            log.warning(f"[Microphone] Sensor {sensor_id} not found in node tree.")
            return {}

        props = sensor.get("properties", {})
        detections = {}
        noise = props.get("noise", 0.0)

        # --- Get sensor pose ---
        pose = find_pose_by_metadata(
            poses,
            cls=sensor.get("class", "").lower(),
            type=sensor.get("type", "").lower(),
            subtype=sensor.get("subtype", "").lower(),
            name=sensor.get("name", "").lower()
        )
        if not pose:
            log.warning(f"[Microphone] Pose not found for {sensor_id}")
            return {}

        # --- Candidate targets ---
        humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
        speakers = find_nodes_by_metadata(nodes, cls="actuator", type="speaker")
        soundsources = find_nodes_by_metadata(nodes, cls="actor", subtype="soundsource")
        robots = find_nodes_by_metadata(nodes, cls="composite", type="robot")
        visible_targets = humans + speakers + soundsources + robots

        for target in visible_targets:
            r = handle_affection_ranged(nodes, poses, log, sensor, target, target.get("subtype"))
            if not r:
                continue

            # compute first
            dist = round(apply_noise(r["distance"], noise), 2)
            rng = r["range"]
            weight = max(0.0, 1.0 - dist / rng)
            signal = round(weight * 100.0, 2)

            det = {
                "class": r["class"],
                "type": r["type"],
                "subtype": r["subtype"],
                "distance": dist,
                "range": rng,
                "signal_strength": signal,
                "audible": True,
            }

            detections[target["name"]] = det
            log.info(f"[Microphone] {sensor_id} detected {target['name']} -> {det}")

        # --- Drop very weak signals ---
        # for k in list(detections.keys()):
        #     if detections[k]["signal_strength"] < 5.0:
        #         detections.pop(k, None)
        #         log.debug(f"[Microphone] Dropped {k} (weak signal)")

        return detections

    except Exception as e:
        log.error(f"handle_microphone_sensor: {e}")
        return {}

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

        targets = (
            find_nodes_by_metadata(nodes, cls="composite", type="robot")
            + find_nodes_by_metadata(nodes, cls="obstacle")
            + find_nodes_by_metadata(nodes, cls="actor")
        )

        nearest = None
        min_dist = float("inf")

        for target in targets:
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
            if not r:
                continue
            d = r["distance"]
            if d < min_dist:
                min_dist = d
                nearest = r
        if not nearest:
            sensed = apply_noise(props.get("range", 0), noise)
            return {"distance": round(sensed, 2)}
        
        sensed = apply_noise(min_dist, noise)
        return {
            "distance": round(min_dist, 2),
            "detected_class": nearest["class"],
            "detected_type": nearest["type"],
            "detected_subtype": nearest["subtype"],
            "detected_name": nearest["name"],
        }

    except Exception as e:
        import traceback
        log.error(f"handle_distance_sensor({sensor_id}) crashed: {e}\n{traceback.format_exc()}")
        raise

# Affected by barcode, color, human, qr, text
def handle_reader_sensor(nodes, poses, log, sensor_id, env_properties=None, env=None):
    """
    Generic handler for active reader-type sensors (camera, RFID, barcode, QR, etc.).
    Decides dynamically what entities are visible or readable.
    Returns:
        dict of detections {target_name: {...}}.
    """
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            log.warning(f"[Reader] Sensor {sensor_id} not found in node tree.")
            return {}

        props = sensor.get("properties", {})
        noise = props.get("noise", 0.0)
        subtype = sensor.get("subtype", "").lower()
        detections = {}

        # --- Get pose ---
        pose = find_pose_by_metadata(
            poses,
            cls=sensor.get("class", "").lower(),
            type=sensor.get("type", "").lower(),
            subtype=subtype,
            name=sensor.get("name", "").lower(),
        )
        if not pose:
            log.warning(f"[Reader] Pose not found for {sensor_id}")
            return {}

        # --- Determine detection domain ---
        if subtype == "camera":
            # Visible light-based
            luminosity = compute_luminosity(nodes, poses, log, sensor_id, env_properties)
            log.info(f"[Reader:Camera] {sensor_id}: local luminosity = {round(luminosity, 2)}")

            humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
            qrs = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="qrcode")
            barcodes = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="barcode")
            texts = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="plaintext")
            colors = find_nodes_by_metadata(nodes, cls="actor", subtype="color")
            leds = find_nodes_by_metadata(nodes, cls="actuator", type="singleled", subtype="led")
            # robots = find_nodes_by_metadata(nodes, cls="composite", type="robot")

            visible_targets = humans + qrs + barcodes + texts + colors + leds # + robots

        elif subtype == "rfid":
            # RFID field-based
            tags = find_nodes_by_metadata(nodes, cls="actor", type="text", subtype="rfidtag")
            visible_targets = tags

        else:
            log.warning(f"[Reader] Unsupported reader subtype '{subtype}'")
            return {}

        # --- Process detections ---
        for target in visible_targets:
            handler = handle_affection_arced if target["class"] != "actuator" else handle_affection_ranged
            r = handler(nodes, poses, log, sensor, target, target.get("subtype"))
            if not r:
                continue
            
            dist = round(apply_noise(r["distance"], noise), 2)
            rng = r["range"]
            name = target["name"]

            det = {
                "class": r["class"],
                "type": r["type"],
                "subtype": r["subtype"],
                "range": rng,
                "angle": round(math.degrees(r.get("angle", 0.0)), 2) if "angle" in r else None,
                "fov": r.get("fov", None),
                "visible": True,
            }

            # --- Camera content extraction ---
            if subtype == "camera":
                tclass = target.get("class", "").lower()
                ttype = target.get("type", "").lower()
                tsub = target.get("subtype", "").lower()
                props_t = target.get("properties", {})

                if tclass == "actor" and ttype == "text":
                    det["content"] = props_t.get("message", "(unreadable)")
                elif tclass == "actor" and tsub == "color":
                    det["color"] = props_t.get("value", "#FFFFFF")
                elif tclass == "actor" and tsub == "qrcode":
                    det["content"] = props_t.get("encoded", "(empty)")

            # --- RFID content extraction ---
            elif subtype == "rfid":
                tclass = target.get("class", "").lower()
                tsub = target.get("subtype", "").lower()
                if tclass == "actor" and tsub == "rfidtag":
                    det["message"] = target.get("properties", {}).get("message", "(empty)")

            detections[name] = det
            log.info(f"[Reader] {sensor_id} detected {name} -> {det}")

        # --- Low light filtering (camera only) ---
        if subtype == "camera" and luminosity < 30 and detections:
            fail_prob = (30 - luminosity) / 30.0
            for k in list(detections.keys()):
                if random.random() < fail_prob:
                    detections.pop(k, None)
                    log.info(f"[Reader:Camera] Dropped {k} due to low light")

        return detections

    except Exception as e:
        log.error(f"handle_reader_sensor({sensor_id}) error: {e}")
        return {}

# Affected by robots
def handle_area_alarm(nodes, poses, log, sensor_id, env_properties=None):
    """Trigger when a robot is within range."""
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            return {"triggered": False, "detections": {}}

        detections = []
        for r in find_nodes_by_metadata(nodes, cls="composite", type="robot"):
            aff = handle_affection_ranged(nodes, poses, log, sensor, r, "robot")
            if aff and aff["distance"] <= aff["range"]:
                detections.append(r["name"])
        return {"triggered": bool(detections), "detections": detections}

    except Exception as e:
        log.error(f"handle_area_alarm({sensor_id}) error: {e}")
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

        sensor = find_node_by_id(nodes, sensor_id)
        if not isinstance(sensor, dict):
            return {"triggered": False, "detections": []}

        shape = sensor.get("shape", {})
        points = shape.get("points", [])
        if len(points) < 2:
            return {"triggered": False, "detections": []}

        pose = find_pose_by_metadata(
            poses,
            cls=sensor.get("class", "").lower(),
            type=sensor.get("type", "").lower(),
            subtype=sensor.get("subtype", "").lower(),
            name=sensor.get("name", "").lower(),
        )
        if not pose:
            log.warning(f"[LinearAlarm] Pose not found for {sensor_id}")
            return {"triggered": False, "detections": []}

        # Compute beam endpoints in world space
        x, y, th = pose["x"], pose["y"], math.radians(pose["theta"])
        def tf_local_to_world(pt):
            return [
                x + pt["x"] * math.cos(th) - pt["y"] * math.sin(th),
                y + pt["x"] * math.sin(th) + pt["y"] * math.cos(th),
            ]

        start, end = tf_local_to_world(points[0]), tf_local_to_world(points[1])

        detections = []
        robots = find_nodes_by_metadata(nodes, cls="composite", type="robot")

        # log.info(f"[LinearAlarm][DEBUG] Beam start={start}, end={end}")
        for rob in robots:
            rob_pose = find_pose_by_metadata(poses, rob["class"], rob["type"], rob.get("subtype"), rob["name"])
            if not rob_pose:
                continue
            world_pts = get_shape_world_points(rob_pose, rob.get("shape", {}))
            if not world_pts or len(world_pts) < 2:
                continue

            # Test each robot edge for intersection
            for a, b in zip(world_pts, world_pts[1:] + [world_pts[0]]):
                if check_lines_intersection(start, end, a, b):
                    detections.append(rob["name"])
                    break

        return {"triggered": bool(detections), "detections": detections}

    except Exception as e:
        import traceback
        log.error(f"handle_linear_alarm({sensor_id}) crashed: {e}\n{traceback.format_exc()}")
        return {"triggered": False, "detections": {}}

# def handle_generic_sensor(nodes, poses, log, sensor_id, env_properties=None):
#     """
#     Generic fallback handler for custom sensors (e.g., gamma, delta).
#     Reads declared 'affections' list and computes combined influence.
#     Returns: {"<subtype>": float}
#     """
#     try:
#         sensor = find_node_by_id(nodes, sensor_id)
#         if not sensor:
#             log.warning(f"[GenericSensor] {sensor_id} not found.")
#             return {}

#         props = sensor.get("properties", {})
#         declared_affections = props.get("affectedBy", [])  # e.g. ["fire", "human"]
#         results = {}

#         for declared in declared_affections:
#             aff = declared.id.lower()
#             disp = declared.dispersion
            
#             # --- dispatch table ---
#             if aff == "temperature":
#                 r = handle_temperature_sensor(nodes, poses, log, sensor_id, env_properties)
#             elif aff == "humidity":
#                 r = handle_humidity_sensor(nodes, poses, log, sensor_id, env_properties)
#             elif aff == "gas":
#                 r = handle_gas_sensor(nodes, poses, log, sensor_id, env_properties)
#             elif aff == "light":
#                 r = handle_light_sensor(nodes, poses, log, sensor_id, env_properties)
#             elif aff == "distance":
#                 r = handle_distance_sensor(nodes, poses, log, sensor_id, env_properties)
#             else:
#                 log.error(f"[GenericSensor] Unknown affectedBy '{aff}' in {sensor_id}")
#                 continue

#             # apply optional dispersion
#             if disp and isinstance(r, dict):
#                 for key, val in r.items():
#                     if isinstance(val, (int, float)) \
#                         and key in ("temperature","humidity","gas","light","distance"):
#                         r[key] = apply_dispersion(val, disp.__class__.__name__.lower(), **disp.__dict__)

#             results.update(r)

#         # if empty -> zero
#         if not results:
#             results = {sensor.get("subtype") or sensor.get("type") or "value": 0.0}

#         return results

#     except Exception as e:
#         log.error(f"handle_generic_sensor({sensor_id}) error: {e}")
#         return {}

def handle_generic_sensor(nodes, poses, log, sensor_id, env_properties=None):
    try:
        sensor = find_node_by_id(nodes, sensor_id)
        if not sensor:
            log.warning(f"[GenericSensor] {sensor_id} not found.")
            return {}

        props = sensor.get("properties", {})
        declared_affections = props.get("affectedBy", [])
        entities = find_nodes_by_metadata(nodes)

        results = {}

        for declared in declared_affections:
            aff = declared.get("id") if isinstance(declared, dict) else getattr(declared, "id", None)
            if not aff:
                continue

            aff = aff.lower()
            base_value = (env_properties or {}).get(aff, props.get("value", 0.0))
            influences = []

            for source in entities:
                if source.get("name") == sensor.get("name"):
                    continue

                if not affects(source, aff):
                    continue

                disp = None
                target_val = None

                for a in source.get("properties", {}).get("affects", []):
                    aid = a.get("id") if isinstance(a, dict) else getattr(a, "id", None)

                    if aid and aid.lower() == aff:
                        disp = a.get("dispersion") if isinstance(a, dict) else getattr(a, "dispersion", None)
                        target_val = a.get("target_value") if isinstance(a, dict) else getattr(a, "target_value", None)
                        break

                if target_val is None:
                    target_val = source.get("properties", {}).get("value", base_value)

                r = handle_affection_ranged(nodes, poses, log, sensor, source, aff, disp)
                if not r:
                    continue

                progress = r.get("progress", 0.0)
                influence = progress * (target_val - base_value)
                influences.append(influence)

            final = base_value + sum(influences)
            results[aff] = round(final, 2)

        if not results:
            key = sensor.get("subtype") or sensor.get("type") or "value"
            results[key.lower()] = props.get("value", 0.0)

        return results

    except Exception as e:
        log.error(f"handle_generic_sensor({sensor_id}) error: {e}")
        return {}

def handle_generic_actuator(nodes, poses, log, actuator_id, env_properties):
    """
    Generic handler for CustomThing actuators.
    Applies effects declared in properties['affects']: list[AffectEntry].
    Returns dict {property: delta_value}.
    """
    actuator = find_node_by_id(nodes, actuator_id)
    if not actuator:
        log.warning(f"[GenericActuator] {actuator_id} not found.")
        return {}

    props = actuator.get("properties", {})
    declared_affections = props.get("affects", [])

    results = {}

    for declared in declared_affections:
        aff = declared.id.lower()
        disp = declared.dispersion
        
        # distance attenuation
        sensor_results = []  # we apply ranged attenuation to all sensors in environment
        sensors = find_nodes_by_metadata(nodes, cls="sensor")

        for s in sensors:
            r = handle_affection_ranged(nodes, poses, log, s, actuator, aff)
            if not r:
                continue
            val = r["value"]

            if disp:
                val = apply_dispersion(
                    val,
                    disp.__class__.__name__.lower(),
                    **disp.__dict__
                )

            sensor_results.append(val)

        if sensor_results:
            results[aff] = sum(sensor_results) / len(sensor_results)
        else:
            results[aff] = 0.0

    return results

def check_affectability(nodes, poses, log, sensor_id, env_properties, env=None):
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

    # Only skip when environment explicitly disables sensor-side computation
    if env is None and (node_subtype in {"camera", "rfid", "microphone"} or node_type in {"camera", "rfid", "microphone"}):
        # log.info(f"[Affectability] Skipping RPC sensor {sensor_id} ({node_type}/{node_subtype})")
        return None

    # log.info(f"[Affectability] Evaluating {node_class}:{node_type}:{node_subtype or ''} -> {node_name}")

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
                detections = handle_microphone_sensor(nodes, poses, log, sensor_id, env_properties, env=env)
                return {"detections": detections, "env_properties": env_properties}
            elif subtype in ("camera", "rfid"):
                detections = handle_reader_sensor(nodes, poses, log, sensor_id, env_properties, env=env)
                return {"detections": detections, "env_properties": env_properties}
            elif subtype == "areaalarm":
                affected = handle_area_alarm(nodes, poses, log, sensor_id)
            elif subtype == "linearalarm":
                affected = handle_linear_alarm(nodes, poses, log, sensor_id)
            elif subtype in ("sonar", "ir"):
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif subtype == "light":
                affected = handle_light_sensor(nodes, poses, log, sensor_id, env_properties)
            else:
                affected = handle_generic_sensor(nodes, poses, log, sensor_id, env_properties)

        # --- Composite sensors (robot-mounted sensors, pantilt, etc.) ---
        elif node_class == "composite" and node_type == "robot":
            subtype = node_subtype or node_name

            if subtype == "microphone":
                affected = handle_microphone_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype in ("camera", "rfid"):
                detections = handle_reader_sensor(nodes, poses, log, sensor_id, env_properties, env=env)
                return {"detections": detections, "env_properties": env_properties}
            elif subtype in ("sonar", "ir"):
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif subtype == "temperature":
                affected = handle_temperature_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "humidity":
                affected = handle_humidity_sensor(nodes, poses, log, sensor_id, env_properties)
            elif subtype == "gas":
                affected = handle_gas_sensor(nodes, poses, log, sensor_id, env_properties)

    except Exception as e:
        log.error(f"[Affectability] Error handling {sensor_id}: {e}")
        raise

    return {
        "affections": affected,
        "env_properties": env_properties
    }
