from os.path import dirname, join


THIS_DIR = dirname(__file__)
MODEL_REPO_PATH = join(THIS_DIR, 'models')
TEMPLATES_PATH = join(THIS_DIR, 'templates')

def log_thing_info(thing):
    components = []

    print(f'[*] Thing model: {thing.name}')
    if hasattr(thing, 'sensors') and hasattr(thing, 'actors') and hasattr(thing, 'actuators'):
        print(f'[*] Installed sensors:')
        for posed_sensor in thing.sensors:
            sensor = posed_sensor.ref
            print(f'    - {sensor.name}: ({sensor.__class__.__name__})')
            components.append((sensor, posed_sensor.name))
        # print(f'[*] Installed actors:')
        # for posed_actor in thing.actors:
        #     actor = posed_actor.ref
        #     print(f'    - {actor.name}: ({actor.__class__.__name__})')
        #     components.append((actor, posed_actor.name))
        print(f'[*] Installed actuators:')
        for posed_actuator in thing.actuators:
            actuator = posed_actuator.ref
            print(f'    - {actuator.name}: ({actuator.__class__.__name__})')
            components.append((actuator, posed_actuator.name))
    else:
        # Atomic thing
        print(f'[*] Atomic Thing: {thing.name} ({thing.__class__.__name__})')
        components.append((thing, thing.name))

    return components
