import math, random
from omnisim.utils.geometry import calc_distance, check_lines_intersection

def handle_affection_ranged(nodes, poses, log, sensor_id, node_id, type_):
    """
    Check if pose_start is within the range of node_id.
    """
    # Sensor info
    sensor = nodes[sensor_id]
    sensor_class = sensor['class']   # should be "sensor"
    sensor_type = sensor.get('type')
    sensor_name = sensor['name']
    sensor_inst = sensor['id']

    # Sensor pose
    if sensor_type:
        pose_start = poses[f"{sensor_class}s"][sensor_type][sensor_name][sensor_inst]
    else:
        pose_start = poses[f"{sensor_class}s"][sensor_name][sensor_inst]
    
    # Target node info
    node = nodes[node_id]
    node_class = node['class']   # "sensor", "actuator", "actor", "composite", "obstacle"
    node_type = node.get('type')     # e.g. "envdevice", "envsensor", "fire"
    node_name = node['name']     # e.g. "thermostat", "temperature", "fire"
    node_inst = node['id']       # instance id, e.g. "th_1"

    # Access pose using full hierarchy
    if node_type:
        pose_end = poses[f"{node_class}s"][node_type][node_name][node_inst]
    else:
        # if no type, flatten one level
        pose_end = poses[f"{node_class}s"][node_name][node_inst]

    # Distance between sensor and target
    dist = calc_distance(
        [pose_start['x'], pose_start['y']],
        [pose_end['x'], pose_end['y']]
    )
    log.info("handle_affection_ranged %s -> dist %.2f", node_id, dist)

    if dist < sensor['properties']['range']:  # within affection range
        result = {
            'name': node_name,
            'id': node_inst,
            'class': node_class,
            'type': node_type,
            'distance': dist,
            'range': sensor['properties']['range'],
        }
        # Merge node properties at top-level
        result.update(node.get('properties', {}))
        return result
    return None

def handle_affection_arced(nodes, poses, log, sensor_id, node_id, type_):
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
        sensor = nodes[sensor_id]
        sensor_class = sensor['class']   # should be "sensor"
        sensor_type = sensor.get('type')
        sensor_name = sensor['name']
        sensor_inst = sensor['id']

        # Sensor pose
        if sensor_type:
            pose_start = poses[f"{sensor_class}s"][sensor_type][sensor_name][sensor_inst]
        else:
            pose_start = poses[f"{sensor_class}s"][sensor_name][sensor_inst]
        
        # Target node info
        node = nodes[node_id]
        node_class = node['class']   # "sensor", "actuator", "actor", "composite", "obstacle"
        node_type = node.get('type')     # e.g. "envdevice", "envsensor", "fire"
        node_name = node['name']     # e.g. "thermostat", "temperature", "fire"
        node_inst = node['id']       # instance id, e.g. "th_1"

        # Access pose using full hierarchy
        if node_type:
            pose_end = poses[f"{node_class}s"][node_type][node_name][node_inst]
        else:
            # if no type, flatten one level
            pose_end = poses[f"{node_class}s"][node_name][node_inst]

        # Distance between sensor and target
        dist = calc_distance(
            [pose_start['x'], pose_start['y']],
            [pose_end['x'], pose_end['y']]
        )
        log.info("handle_affection_arced %s -> dist %.2f", node_id, dist)

        if dist < sensor["properties"]['range']:  # within affection range
            # Check if in specific arc
            fov = sensor["properties"]['fov'] / 180.0 * math.pi
            min_a = pose_start['theta'] - fov / 2
            max_a = pose_start['theta'] + fov / 2
            pose_end_ang = math.atan2(pose_end['y'] - pose_start['y'], pose_end['x'] - pose_start['x'])
            # print(min_a, max_a, pose_end_ang)
            ok = False
            ang = None
            if min_a < pose_end_ang < max_a:
                ok = True
                ang = pose_end_ang
            elif min_a < (pose_end_ang + 2 * math.pi) and (pose_end_ang + 2 * math.pi) < max_a:
                ok = True
                ang = pose_end_ang + 2 * math.pi
            elif min_a < (pose_end_ang - 2 * math.pi) and (pose_end_ang - 2 * math.pi) < max_a:
                ok = True
                ang = pose_end_ang + 2 * math.pi

            if ok:
                props = None
                if type_ == 'robot':
                    props = node_id
                    name = node_id
                    id_ = None
                else:
                    props = nodes[node_id]["properties"]
                    name = nodes[node_id]['name']
                    id_ = nodes[node_id]['id']
                return {
                    "class": node_class,
                    "type": type_,
                    'name': name,
                    'id': id_,
                    "info": props,
                    'distance': dist,
                    'min_sensor_ang': min_a,
                    'max_sensor_ang': max_a,
                    'actor_ang': ang,
                }

        return None

def handle_temperature_sensor(nodes, poses, log, sensor_id):
    """
    Handles the temperature data for an environmental sensor.
    Influences: thermostats (actuators.envdevice.thermostat) and fires (actors.envactor.fire).
    """
    try:
        temperatures = {}
        # --- Thermostat influences ---
        for node_id in nodes['actuators']['envdevice']['thermostat']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'thermostat')
            if r is not None:
                temperatures[node_id] = r

        # --- Fire influences ---
        for node_id in nodes['actors']['envactor']['fire']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'fire')
            if r is not None:
                temperatures[node_id] = r

        return temperatures
    except Exception as e:
        log.error(str(e))
        raise Exception(str(e)) from e

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
        humidities = {}
        # --- Humidifier influences ---
        for node_id in nodes['actuators']['envdevice']['humidifier']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'humidifier')
            if r is not None:
                humidities[node_id] = r

        # --- Water influences ---
        for node_id in nodes['actors']['envactor']['water']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'water')
            if r is not None:
                humidities[node_id] = r
        return humidities
    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

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
        gases = {}
        # --- Human influences ---
        for node_id in nodes['actors']['human']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'human')
            if r is not None:
                gases[node_id] = r
                
        # --- Fire influences ---
        for node_id in nodes['actors']['envactor']['fire']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'fire')
            if r is not None:
                gases[node_id] = r

    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

    return gases

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
        sounds = {}
        # - actuator speaker
        for node_id in nodes['actuators']['speaker']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'speaker')
            if r is not None:
                sounds[node_id] = r
        # - actor human
        for node_id in nodes['actors']['human']:
            if nodes[node_id]['properties']['sound'] == 1:
                r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'human')
                if r is not None:
                    sounds[node_id] = r
        # - actor sound sources
        for node_id in nodes['actors']['soundsource']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'soundsource')
            if r is not None:
                sounds[node_id] = r
    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

    return sounds

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
        lights = {}
        # - actuator led
        for node_id in nodes['actuators']['singleled']['led']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'led')
            if r is not None:
                lights[node_id] = r
        # - actor fire
        for node_id in nodes['actors']['envactor']['fire']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'fire')
            if r is not None:
                lights[node_id] = r
    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

    return lights

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
        detections = {}
        # - actor human
        for node_id in nodes['actors']['human']:
            r = handle_affection_arced(nodes, poses, log, sensor_id, node_id, 'human')
            if r is not None:
                detections[node_id] = r
        # - actor qr
        for node_id in nodes['actors']['text']['qrcode']:
            r = handle_affection_arced(nodes, poses, log, sensor_id, node_id, 'qrcode')
            if r is not None:
                detections[node_id] = r
        # - actor barcode
        for node_id in nodes['actors']['text']['barcode']:
            r = handle_affection_arced(nodes, poses, log, sensor_id, node_id, 'barcode')
            if r is not None:
                detections[node_id] = r
        # - actor text
        for node_id in nodes['actors']['text']['plaintext']:
            r = handle_affection_arced(nodes, poses, log, sensor_id, node_id, 'plaintext')
            if r is not None:
                detections[node_id] = r
        # - actor color
        for node_id in nodes['actors']['color']:
            r = handle_affection_arced(nodes, poses, log, sensor_id, node_id, 'color')
            if r is not None:
                detections[node_id] = r
        # - actuator led
        for node_id in nodes['actuators']['singleled']['led']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'led')
            if r is not None:
                detections[node_id] = r

        # check all robots
        if with_robots:
            for node_id in nodes['composites']['robot']:
                r = handle_affection_arced(nodes, poses, log, sensor_id, node_id, 'robot')
                if r is not None:
                    detections[node_id] = r
    except Exception as e: # pylint: disable=broad-except
        log.error("handle_camera_sensor: %s", str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

    return detections

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
        rfids = {}
        for node_id in nodes['actors']['text']['rfidtag']:
            r = handle_affection_arced(nodes, poses, log, sensor_id, node_id, 'rfid_tag')
            if r is not None:
                rfids[node_id] = r

    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

    return rfids

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
        detections = {}
        # Check all robots if in there
        for node_id in nodes['composites']['robot']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'robot')
            if r is not None:
                detections[node_id] = r
    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e
    return detections

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
        distances = {}
        # Check all robots if in there
        for node_id in nodes['composites']['robot']:
            r = handle_affection_ranged(nodes, poses, log, sensor_id, node_id, 'robot')
            if r is not None:
                distances[node_id] = r
    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

    return distances

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
        line_start = nodes[sensor_id]['pose']['start']
        line_end = nodes[sensor_id]['pose']['end']
        start = [line_start['x'], line_start['y']]
        end = [line_end['x'], line_end['y']]
        
        detected = {}
        # Check all robots
        for node_id in nodes['composites']['robot']:
            robot_pose = [poses[node_id]['x'], poses[node_id]['y']]

            if node_id not in lin_alarms_robots[sensor_id]:
                lin_alarms_robots[sensor_id][node_id] = {
                    "prev": robot_pose,
                    "curr": robot_pose
                }

            lin_alarms_robots[sensor_id][node_id]["prev"] = \
                lin_alarms_robots[sensor_id][node_id]["curr"]

            lin_alarms_robots[sensor_id][node_id]["curr"] = robot_pose

            intersection = check_lines_intersection(start, end, \
                lin_alarms_robots[sensor_id][node_id]["prev"],
                lin_alarms_robots[sensor_id][node_id]["curr"]
            )

            if intersection is True:
                detected[node_id] = intersection

    except Exception as e:
        log.error(str(e))
        # pylint: disable=broad-exception-raised
        raise Exception(str(e)) from e

    return detected

def check_affectability(nodes, poses, log, env_properties, sensor_id, lin_alarms_robots=None):
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
    if sensor_id not in nodes:
        raise Exception(f"{sensor_id} not in devices")

    node_class = nodes[sensor_id]["class"]   # sensor / actuator / actor / composite
    node_name = nodes[sensor_id]["name"]

    affected = {}
    try:
        if node_class == "sensor":
            if node_name == "temperature":
                affected = handle_temperature_sensor(nodes, poses, log, sensor_id)
            elif node_name == "humidity":
                affected = handle_humidity_sensor(nodes, poses, log, sensor_id)
            elif node_name == "gas":
                affected = handle_gas_sensor(nodes, poses, log, sensor_id)
            elif node_name == "microphone":
                affected = handle_microphone_sensor(nodes, poses, log, sensor_id)
            elif node_name == "camera":
                affected = handle_camera_sensor(nodes, poses, log, sensor_id)
            elif node_name == "areaalarm":
                affected = handle_area_alarm(nodes, poses, log, sensor_id)
            elif node_name == "linearalarm":
                affected = handle_linear_alarm(nodes, poses, log, sensor_id, lin_alarms_robots)
            elif node_name in ["sonar", "ir"]:
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif node_name == "light":
                affected = handle_light_sensor(nodes, poses, log, sensor_id)
        elif node_name == "robot":
            if node_name == "microphone":
                affected = handle_microphone_sensor(nodes, poses, log, sensor_id)
            elif node_name == "camera":
                affected = handle_camera_sensor(nodes, poses, log, sensor_id)
            elif node_name == "rfid":
                affected = handle_rfid_sensor(nodes, poses, log, sensor_id)
            elif node_name in ["sonar", "ir"]:
                affected = handle_distance_sensor(nodes, poses, log, sensor_id)
            elif node_name == "envcombo":  # e.g. temp/hum/gas multipurpose robot sensor
                affected = {
                    "temperature": handle_temperature_sensor(nodes, poses, log, sensor_id),
                    "humidity": handle_humidity_sensor(nodes, poses, log, sensor_id),
                    "gas": handle_gas_sensor(nodes, poses, log, sensor_id),
                }
    except Exception as e:
        log.error(f"Error in device handling for {sensor_id}: {e}")
        raise
    return {
        "affections": affected,
        "env_properties": env_properties
    }