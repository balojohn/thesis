# from os.path import basename
import jinja2

# from omnisim.lang import build_model
# from omnisim.lang import get_entity_mm

from ..utils import TEMPLATES_PATH

SENSOR_CLASSES = [
        'rangefinder', 'reader', 'alarm', 'microphone', 'light', 'imu', 'lidar'
    ]

ACTUATOR_CLASSES = [
    'pantilt', 'envdevice', 'relay', 'singlebutton', 'buttonarray',
    'led', 'singleled', 'ledarray', 'speaker'
]

ACTOR_CLASSES = [
    'soundsource', 'color', 'text', 'envactor', 'human'
]

# Initialize template engine
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    trim_blocks=True,
    lstrip_blocks=True
)

entities_tpl = jinja_env.get_template('entity_model.jinja')

def build_entity_model(context):
    modelf = entities_tpl.render(context)
    return modelf

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
        # for posed_actor in actor:
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


def map_thing_to_entity_type(component):
    cls_name = component.__class__.__name__.lower()

    if cls_name in SENSOR_CLASSES:
        return 'sensor'
    elif cls_name in ACTUATOR_CLASSES:
        return 'actuator'
    elif cls_name in ACTOR_CLASSES:
        return 'actor'
    else:
        print(f"[WARNING] Unrecognized component type '{cls_name}'. Defaulting to 'actor'.")
        return 'actor'


def extract_entities(components):
    sensors = []
    actors = []
    actuators = []

    for component, name in components:
        _cls = map_thing_to_entity_type(component)
        uri = f'{_cls}.{component.__class__.__name__.lower()}.{name.lower()}'
        pubFreq = getattr(component, 'pubFreq', None)
        attrs = []

        if hasattr(component, 'dataModel') and component.dataModel:
            for a in component.dataModel.properties:
                value = getattr(component, a.name, None)
                attrs.append((a.name, str(a.type), value))
        _entry = {
            'name': name,
            'type': _cls,
            'topic': uri,
            'pubFreq': pubFreq,
            'attributes': attrs
        }

        if _cls == 'sensor':
            sensors.append(_entry)
        elif _cls == 'actuator':
            actuators.append(_entry)
        else:
            actors.append(_entry)

    return {
        'sensors': sensors,
        'actors': actors,
        'actuators': actuators
    }

def thing_to_entity_m2m(thing):
    components = log_thing_info(thing)
    ent = extract_entities(components)
    m = build_entity_model(ent)
    return m