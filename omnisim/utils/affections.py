import math, random
from omnisim.utils.utils import apply_noise
from omnisim.utils.geometry import calc_distance, check_lines_intersection

def find_pose_by_metadata(poses_section, cls, type_, subtype, name):
    """
    Recursively search for an entity pose in poses_section
    matching the given metadata.
    """
    if not isinstance(poses_section, dict):
        return None

    # --- Direct level matches ---
    # e.g. poses['sensors']['envsensor']['temperature']['te_1']
    if cls + "s" in poses_section:
        poses_section = poses_section[cls + "s"]

    # Try type/subtype/names in different combinations
    for key, val in poses_section.items():
        if key == type_ and isinstance(val, dict):
            # e.g. ['envsensor'] or ['robot']
            res = find_pose_by_metadata(val, cls, type_, subtype, name)
            if res:
                return res
        elif key == subtype and isinstance(val, dict):
            # e.g. ['temperature'], ['sonar']
            if name in val:
                pose = val[name]
                if isinstance(pose, dict) and all(k in pose for k in ("x", "y", "theta")):
                    return pose
            else:
                res = find_pose_by_metadata(val, cls, type_, subtype, name)
                if res:
                    return res
        elif key == name and isinstance(val, dict):
            if all(k in val for k in ("x", "y", "theta")):
                return val
            elif "rel_pose" in val:
                # relative pose only, skip (not an absolute one)
                continue
        elif isinstance(val, dict):
            res = find_pose_by_metadata(val, cls, type_, subtype, name)
            if res:
                return res
    return None

def find_nodes_by_metadata(nodes_section, cls=None, type_=None, subtype=None):
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
            (type_ is None or t == type_) and
            (subtype is None or st == subtype)):
            found.append(nodes_section)

    # Recurse into nested dicts
    for val in nodes_section.values():
        if isinstance(val, dict):
            found.extend(find_nodes_by_metadata(val, cls, type_, subtype))
    return found

def handle_affection_ranged(nodes, poses, log, sensor: dict, node: dict, type_):
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

def handle_affection_arced(nodes, poses, log, sensor, node, type_):
    """
    Handles the affection of an arced sensor.
    This method calculates the distance between two points and checks if the 
    second point (node_id) is within the range and field of view (FOV) of the first 
    point (pose_start). If the second point is within the range and FOV, it returns 
    a dictionary with information about the affection.
    Args:
        sensor_id (str): The name of the first point (sensor).
        node_id (str): The name of the second point (target).
        type (str): The type of the second point (e.g., "robot" or other).
    Returns:
        dict or None: A dictionary containing information about the affection 
        if the second point is within range and FOV, otherwise None. The 
        dictionary contains the following keys:
            - 'type': The type of the second point.
            - 'info': Properties of the second point.
            - 'distance': The distance between the two points.
            - 'min_sensor_ang': The minimum angle of the sensor's FOV.
            - 'max_sensor_ang': The maximum angle of the sensor's FOV.
            - 'actor_ang': The angle of the second point relative to the first.
            - 'name': The name of the second point.
            - 'id': The ID of the second point (if applicable).
    """
    # Sensor info
    sensor_class = sensor.get("class", "").lower()          # e.g. "sensor"
    sensor_type = sensor.get("type", "").lower() or None    # e.g. "rangefinder"
    sensor_subtype = sensor.get("subtype", "").lower() or None
    sensor_name = sensor.get("name", "").lower()

    pose_start = find_pose_by_metadata(poses, sensor_class, sensor_type, sensor_subtype, sensor_name)
    if not pose_start:
        log.warning(f"[Affection] Pose not found for arced sensor {sensor_name}")
        return None

    # Target node info
    node_class = node.get("class", "").lower()              # e.g. "actor", "composite", "sensor"
    node_type = node.get("type", "").lower() or None
    node_subtype = node.get("subtype", "").lower() or None
    node_name = node.get("name", "").lower()
    node_id = node.get("id", node_name)

    pose_end = find_pose_by_metadata(poses, node_class, node_type, node_subtype, node_name)
    if not pose_end:
        log.warning(f"[Affection] Pose not found for target {node_name}")
        return None
    
    # Distance between sensor and target
    dist = calc_distance(
        [pose_start['x'], pose_start['y']],
        [pose_end['x'], pose_end['y']]
    )
    sensor_props = sensor.get("properties", {})
    sensor_range = sensor_props.get("range", 0)
    fov_deg = sensor_props.get("fov", 0)
    fov_rad = math.radians(fov_deg)
    log.info(f"[Affection:Arced] {sensor_name} -> {node_name} | dist={dist:.2f}, range={sensor_range}, FOV={fov_deg}")

    if dist > sensor_range:
        return None  # Out of range

    # === Angle / FOV check ===
    # Convert sensor and target to angles
    theta_s = math.radians(pose_start["theta"])
    dx = pose_end["x"] - pose_start["x"]
    dy = pose_end["y"] - pose_start["y"]
    actor_ang = math.atan2(dy, dx)

    # Normalize to [-π, π]
    def normalize_angle(a):
        return (a + math.pi) % (2 * math.pi) - math.pi

    min_a = normalize_angle(theta_s - fov_rad / 2)
    max_a = normalize_angle(theta_s + fov_rad / 2)
    actor_ang_n = normalize_angle(actor_ang)

    # Check if actor_ang lies within [min_a, max_a], handling wraparound
    def in_fov(min_a, max_a, angle):
        if min_a <= max_a:
            return min_a <= angle <= max_a
        return angle >= min_a or angle <= max_a

    if in_fov(min_a, max_a, actor_ang_n):
        result = {
            "class": node_class,
            "type": node_type,
            "subtype": node_subtype,
            "name": node_name,
            "id": node_id,
            "distance": dist,
            "min_sensor_ang": min_a,
            "max_sensor_ang": max_a,
            "actor_ang": actor_ang_n,
            "range": sensor_range,
            "fov": fov_deg,
        }
        result.update(node.get("properties", {}))
        return result

    return None

def handle_temperature_sensor(nodes, poses, log, sensor_id, env_properties=None):
    """
    Compute the resulting temperature reading for an environmental sensor.
    Influences: thermostats (actuators.envdevice.thermostat) and fires (actors.envactor.fire).
    Returns: {"temperature": float}
    """
    try:
        sensor = nodes[sensor_id]
        props = sensor.get("properties", {})
        env_temp = (env_properties or {}).get("temperature", 25.0)
        influences = []
        noise = props.get("noise", 0.0)  # sensor-specific noise amplitude

        thermostats = find_nodes_by_metadata(nodes, cls="actuator", type_="envdevice", subtype="thermostat")
        fires = find_nodes_by_metadata(nodes, cls="actor", type_="envactor", subtype="fire")

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
def handle_humidity_sensor(nodes, poses, log, sensor_id):
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
        sensor = nodes[sensor_id]
        humidities = {}

        humidifiers = find_nodes_by_metadata(nodes, cls="actuator", type_="envdevice", subtype="humidifier")
        waters = find_nodes_by_metadata(nodes, cls="actor", type_="envactor", subtype="water")

        for target in humidifiers + waters:
            target_id = target["name"]
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "humidity")
            if r:
                humidities[target_id] = r
        return humidities
    except Exception as e:
        log.error(f"handle_humidity_sensor: {e}")
        raise

# Affected by humans and fires
def handle_gas_sensor(nodes, poses, log, sensor_id):
    """
    Handles the environmental sensor for gas detection.
    This method processes the environmental sensor data for gas detection by 
    determining the effect of various actors (humans and fire) on the sensor 
    based on their proximity.
    Args:
        name (str): The name of the place where the sensor is located.
    Returns:
        dict: A dictionary containing the actors and their respective effects 
              on the sensor.
    Raises:
        Exception: If an error occurs during the processing, it logs the error and 
                    raises an exception with the error message.
    """
    try:
        sensor = nodes[sensor_id]
        gases = {}

        humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
        fires = find_nodes_by_metadata(nodes, cls="actor", type_="envactor", subtype="fire")

        for target in humans + fires:
            target_id = target["name"]
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "gas")
            if r:
                gases[target_id] = r
        return gases
    except Exception as e:
        log.error(f"handle_gas_sensor: {e}")
        raise

# Affected by humans with sound, sound sources, speakers (when playing smth),
# robots (when moving)
def handle_microphone_sensor(nodes, poses, log, sensor_id):
    """
    Handles the microphone sensor for a given place name.
    This method processes the microphone sensor data for a specified place,
    identifying and handling sound-related information for human actors and
    sound sources within the range of the microphone.
    Args:
        name (str): The name of the place where the microphone sensor is located.
    Returns:
        dict: A dictionary containing the affected human actors and sound sources
                within the range of the microphone. The keys are the identifiers of
                the actors or sound sources, and the values are the results of the
                affection handling.
    Raises:
        Exception: If an error occurs during the processing, an exception is raised
                    and logged.
    """
    try:
        sensor = nodes[sensor_id]
        sounds = {}

        speakers = find_nodes_by_metadata(nodes, cls="actuator", subtype="speaker")
        humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
        soundsources = find_nodes_by_metadata(nodes, cls="actor", subtype="soundsource")

        for target in speakers:
            target_id = target["name"]
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "speaker")
            if r:
                sounds[target_id] = r

        for target in humans:
            if target.get("properties", {}).get("sound") == 1:
                target_id = target["name"]
                r = handle_affection_ranged(nodes, poses, log, sensor, target, "human")
                if r:
                    sounds[target_id] = r

        for target in soundsources:
            target_id = target["name"]
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "soundsource")
            if r:
                sounds[target_id] = r

        return sounds
    except Exception as e:
        log.error(f"handle_microphone_sensor: {e}")
        raise

# def compute_luminosity(nodes, poses, log, env_name, name, print_debug = False):
#     """
#     Compute the luminosity at a given place identified by `name`.
#     This method calculates the luminosity at a specific location by considering
#     the contributions from environmental light sources, robot LEDs, and actor fires.
#     It also factors in the environmental luminosity and ensures the final luminosity
#     value is within the range [0, 100]. Optionally, it can print debug information
#     during the computation process.
#     Args:
#         name (str): The name of the place for which to compute the luminosity.
#         print_debug (bool, optional): If True, prints debug information. Defaults to False.
#     Returns:
#         float: The computed luminosity value, with a small random variation added.
#     """
#     lum = 0
#     sensor_pose = [poses["sensors"][name]['x'], poses["sensors"][name]['y']]

#     if print_debug:
#         log.info("Computing luminosity for %s", name)

#     # - env light
#     for node in nodes['sensor']['light']:
#         r = handle_affection_ranged(sensor_pose, node, 'light')
#         if r is not None:
#             # th_t = effectors_get_rpcs[node].call({})
#             new_r = r
#             # new_r['info'] = th_t
#             rel_range = 1 - new_r['distance'] / new_r['range']
#             lum += rel_range * new_r['info']['luminosity']
#             if print_debug:
#                 log.info("\t%s - %s", node, new_r['info']['luminosity'])
#     # - robot leds
#     for node in nodes['robot']['actuator']['leds']:
#         r = handle_affection_ranged(sensor_pose, node, 'light')
#         if r is not None:
#             # th_t = effectors_get_rpcs[node].call({})
#             new_r = r
#             # new_r['info'] = th_t
#             rel_range = 1 - new_r['distance'] / new_r['range']
#             lum += rel_range * new_r['info']['luminosity']
#             if print_debug:
#                 log.info("\t%s - %s", node, new_r['info']['luminosity'])
#     # - actor fire
#     for node in nodes['actor']['fire']:
#         r = handle_affection_ranged(sensor_pose, node, 'fire')
#         if r is not None:
#             rel_range = 1 - r['distance'] / r['range']
#             lum += 100 * rel_range
#             if print_debug:
#                 log.info("\t%s - 100", node)

#     env_luminosity = env_name['properties']
#     if print_debug:
#         log.info("\tEnv luminosity: %s", env_luminosity)

#     if lum < env_luminosity:
#         lum = lum * 0.1 + env_luminosity
#     else:
#         lum = env_luminosity * 0.1 + lum

#     if lum > 100:
#         lum = 100
#     if lum < 0:
#         lum = 0

#     if print_debug:
#         log.info("\tComputed luminosity: %s", lum)

#     return lum + random.uniform(-0.25, 0.25)

# Affected by light, fire
def handle_light_sensor(nodes, poses, log, sensor_id):
    """
    Handles the light sensor for a given place.
    This method processes the light sensor data for a specified place
    by calculating the affection range of light and fire actuators and retrieving
    relevant information from the effectors.
    Args:
        name (str): The name of the place to handle the light sensor for.
    Returns:
        dict: A dictionary containing the processed data for light and fire actuators
                that affect the specified place.
    Raises:
        Exception: If an error occurs during processing, an exception is raised and logged.
    """
    try:
        sensor = nodes[sensor_id]
        lights = {}

        leds = find_nodes_by_metadata(nodes, cls="actuator", type_="singleled", subtype="led")
        fires = find_nodes_by_metadata(nodes, cls="actor", type_="envactor", subtype="fire")

        for target in leds + fires:
            target_id = target["name"]
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "light")
            if r:
                lights[target_id] = r
        return lights
    except Exception as e:
        log.error(f"handle_light_sensor: {e}")
        raise

# Affected by barcode, color, human, qr, text
def handle_camera_sensor(nodes, poses, log, sensor_id, with_robots = False):
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
        sensor = nodes[sensor_id]
        detections = {}

        humans = find_nodes_by_metadata(nodes, cls="actor", subtype="human")
        qrs = find_nodes_by_metadata(nodes, cls="actor", type_="text", subtype="qrcode")
        barcodes = find_nodes_by_metadata(nodes, cls="actor", type_="text", subtype="barcode")
        texts = find_nodes_by_metadata(nodes, cls="actor", type_="text", subtype="plaintext")
        colors = find_nodes_by_metadata(nodes, cls="actor", subtype="color")
        leds = find_nodes_by_metadata(nodes, cls="actuator", type_="singleled", subtype="led")
        robots = find_nodes_by_metadata(nodes, cls="composite", type_="robot") if with_robots else []

        for target in humans + qrs + barcodes + texts + colors + leds + robots:
            handler = handle_affection_arced if target["class"] != "actuator" else handle_affection_ranged
            target_id = target["name"]
            r = handler(nodes, poses, log, sensor, target, target.get("subtype"))
            if r:
                detections[target_id] = r

        return detections
    except Exception as e:
        log.error(f"handle_camera_sensor: {e}")
        raise

# Affected by rfid_tags
def handle_rfid_sensor(nodes, poses, log, sensor_id):
    """
    Handles the RFID reader sensor data for a given place name.
    This method processes the RFID reader sensor data associated with a specific place
    identified by the given name. It retrieves the absolute position (x, y) and orientation 
    (theta) of the place, and then processes the RFID tags associated with actors in that place.
    Args:
        name (str): The name of the place to handle the RFID reader sensor data for.
    Returns:
        dict: A dictionary containing the processed RFID tag data for actors in the specified 
        place.
    Raises:
        Exception: If an error occurs during the processing of the RFID reader sensor data.
    """
    try:
        sensor = nodes[sensor_id]
        rfids = {}

        tags = find_nodes_by_metadata(nodes, cls="actor", type_="text", subtype="rfidtag")

        for target in tags:
            target_id = target["name"]
            r = handle_affection_arced(nodes, poses, log, sensor, target, "rfid_tag")
            if r:
                rfids[target_id] = r
        return rfids
    except Exception as e:
        log.error(f"handle_rfid_sensor: {e}")
        raise

# Affected by robots
def handle_area_alarm(nodes, poses, log, sensor_id):
    """
    Handle area alarm for a given place name.
    This method checks if any robots are within the specified range of the given place.
    If a robot is within range, it adds the robot's name and its distance from the place
    to the return dictionary.
    Args:
        name (str): The name of the place to check for area alarms.
    Returns:
        dict: A dictionary where the keys are the names of the robots within range,
                and the values are dictionaries containing the distance of the robot
                from the place and the range.
    Raises:
        Exception: If an error occurs during the process, it logs the error and raises 
        an exception.
    """
    try:
        sensor = nodes[sensor_id]
        detections = {}

        robots = find_nodes_by_metadata(nodes, cls="composite", type_="robot")

        for target in robots:
            target_id = target["name"]
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "robot")
            if r:
                detections[target_id] = r
        return detections
    except Exception as e:
        log.error(f"handle_area_alarm: {e}")
        raise

# Affected by robots
def handle_distance_sensor(nodes, poses, log, sensor_id):
    """
    Calculate the distance of all robots from a specified place and determine if they are 
    within range.
    Args:
        name (str): The name of the place to check distances from.
    Returns:
        dict: A dictionary where the keys are robot names and the values are dictionaries 
        containing:
            - "distance" (float): The distance of the robot from the specified place.
            - "range" (float): The range within which the robot is considered to be.
    Raises:
        Exception: If an error occurs during the calculation, it logs the error and raises an 
        Exception.
    """
    try:
        sensor = nodes[sensor_id]
        distances = {}

        robots = find_nodes_by_metadata(nodes, cls="composite", type_="robot")

        for target in robots:
            target_id = target["name"]
            r = handle_affection_ranged(nodes, poses, log, sensor, target, "robot")
            if r:
                distances[target_id] = r
        return distances
    except Exception as e:
        log.error(f"handle_distance_sensor: {e}")
        raise

# Affected by robots
def handle_linear_alarm(nodes, poses, log, sensor_id, lin_alarms_robots):
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
        sensor = nodes[sensor_id]
        # --- Find start/end poses ---
        line_start = sensor.get("pose", {}).get("start")
        line_end = sensor.get("pose", {}).get("end")
        if not line_start or not line_end:
            log.warning(f"[LinearAlarm] Missing start/end pose for {sensor_id}")
            return {}

        start = [line_start["x"], line_start["y"]]
        end = [line_end["x"], line_end["y"]]

        detected = {}
        robots = find_nodes_by_metadata(nodes, cls="composite", type_="robot")
        # Check all robots
        for robot in robots:
            robot_name = robot.get("name")
            robot_pose = find_pose_by_metadata(
                poses,
                cls="composite",
                type_="robot",
                subtype=None,
                name=robot_name
            )
            if not robot_pose:
                log.warning(f"[LinearAlarm] Missing pose for robot {robot_name}")
                continue

            curr = [robot_pose["x"], robot_pose["y"]]
            prev = lin_alarms_robots.get(sensor_id, {}).get(robot_name, {}).get("curr", curr)

            # Initialize tracking entry if missing
            lin_alarms_robots.setdefault(sensor_id, {}).setdefault(robot_name, {
                "prev": curr,
                "curr": curr
            })

            # Shift prev->curr
            lin_alarms_robots[sensor_id][robot_name]["prev"] = lin_alarms_robots[sensor_id][robot_name]["curr"]
            lin_alarms_robots[sensor_id][robot_name]["curr"] = curr

            # Check if robot’s segment intersects the linear alarm area
            intersection = check_lines_intersection(
                start, end,
                lin_alarms_robots[sensor_id][robot_name]["prev"],
                lin_alarms_robots[sensor_id][robot_name]["curr"]
            )

            if intersection:
                detected[robot_name] = True
                log.info(f"[LinearAlarm] Robot {robot_name} crossed linear region {sensor_id}")

        return detected
    except Exception as e:
        log.error(f"[LinearAlarm] {e}")
        raise

def check_affectability(nodes, poses, log, sensor_id, env_properties, lin_alarms_robots=None):
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
                affected = handle_temperature_sensor(nodes, poses, log, sensor_id)
            elif subtype == "humidity":
                affected = handle_humidity_sensor(nodes, poses, log, sensor_id)
            elif subtype == "gas":
                affected = handle_gas_sensor(nodes, poses, log, sensor_id)
            elif subtype == "microphone":
                affected = handle_microphone_sensor(nodes, poses, log, sensor_id)
            elif subtype == "camera":
                affected = handle_camera_sensor(nodes, poses, log, sensor_id)
            elif subtype == "rfid":
                affected = handle_rfid_sensor(nodes, poses, log, sensor_id)
            elif subtype == "areaalarm":
                affected = handle_area_alarm(nodes, poses, log, sensor_id)
            elif subtype == "linearalarm":
                affected = handle_linear_alarm(nodes, poses, log, sensor_id, lin_alarms_robots)
            elif subtype in ("sonar", "ir"):
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif subtype == "light":
                affected = handle_light_sensor(nodes, poses, log, sensor_id)

        # --- Composite sensors (robot-mounted sensors, pantilt, etc.) ---
        elif node_class == "composite" and node_type == "robot":
            subtype = node_subtype or node_name

            if subtype == "microphone":
                affected = handle_microphone_sensor(nodes, poses, log, sensor_id)
            elif subtype == "camera":
                affected = handle_camera_sensor(nodes, poses, log, sensor_id)
            elif subtype == "rfid":
                affected = handle_rfid_sensor(nodes, poses, log, sensor_id)
            elif subtype in ("sonar", "ir", "rangefinder"):
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif subtype == "envcombo":
                affected = {
                    "temperature": handle_temperature_sensor(nodes, poses, log, sensor_id),
                    "humidity": handle_humidity_sensor(nodes, poses, log, sensor_id),
                    "gas": handle_gas_sensor(nodes, poses, log, sensor_id),
                }

        # --- Optional: pure actuator or actor cases could go here in future ---

    except Exception as e:
        log.error(f"[Affectability] Error handling {sensor_id}: {e}")
        raise

    return {
        "affections": affected,
        "env_properties": env_properties
    }
