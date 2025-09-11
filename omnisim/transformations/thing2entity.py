# from os.path import basename
import jinja2

# from omnisim.lang import build_model
# from omnisim.lang import get_entity_mm

from ..utils.utils import TEMPLATES_PATH

SENSOR_CLASSES = [
        'rangefinder', 'reader', 'alarm', 'microphone', 'light', 'imu', 'lidar'
    ]

ACTUATOR_CLASSES = [
    'pantilt', 'envdevice', 'relay', 'button', 'buttonarray',
    'led', 'ledarray', 'speaker'
]

ACTOR_CLASSES = [
    'soundsource', 'color', 'text', 'envactor', 'human'
]

# Initialize template engine
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True
)

entities_tpl = jinja_env.get_template('entity_model.jinja')

def build_entity_model(context):
    modelf = entities_tpl.render(context)
    return modelf

def log_thing_info(model):
    components = []

    print(f'[*] Model: {model.name} ({model.__class__.__name__})')

    # Sensors
    if hasattr(model, 'sensors'):
        print(f'[*] Installed sensors:')
        for posed_sensor in model.sensors:
            sensor = posed_sensor.ref
            print(f'    - {sensor.name}: ({sensor.__class__.__name__})')
            components.append((sensor, getattr(posed_sensor, 'name', sensor.name)))

    # Actuators
    if hasattr(model, 'actuators'):
        print(f'[*] Installed actuators:')
        for posed_actuator in model.actuators:
            actuator = posed_actuator.ref
            print(f'    - {actuator.name}: ({actuator.__class__.__name__})')
            components.append((actuator, getattr(posed_actuator, 'name', actuator.name)))

    # Nested Composites
    if hasattr(model, 'composites'):
        print(f'[*] Nested composites:')
        for posed_cthing in model.composites:
            cthing = posed_cthing.ref
            print(f'    - {cthing.name}: ({cthing.__class__.__name__})')
            # recurse to dive into its children
            components.extend(log_thing_info(cthing))

    # Atomic fallback
    if not (hasattr(model, 'sensors') or hasattr(model, 'actuators') or hasattr(model, 'composites')):
        print(f'[*] Atomic: {model.name} ({model.__class__.__name__})')
        components.append((model, model.name))

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
        uri = f"{_cls}.{component.__class__.__name__.lower()}.{component.name.lower()}"
        pubFreq = getattr(component, 'pubFreq', None)
        attrs = []

        if hasattr(component, 'dataModel') and component.dataModel:
            for a in component.dataModel.properties:
                value = getattr(component, a.name, None)
                attrs.append((a.name, str(a.type), value))

        # Add noise attributes if any
        if hasattr(component, 'noise') and component.noise:
            noise_type = component.noise.__class__.__name__
            if noise_type == "Gaussian":
                attrs.append(("noise_mean", "float", component.noise.mean))
                attrs.append(("noise_std", "float", component.noise.std))
            elif noise_type == "Uniform":
                attrs.append(("noise_min", "float", component.noise.min))
                attrs.append(("noise_max", "float", component.noise.max))
            elif noise_type == "CustomNoise":
                attrs.append(("noise_type", "string", component.noise.type))
                attrs.append(("noise_params", "string", component.noise.params))
        
        _entry = {
            'name': name or getattr(component, 'name', 'Unnamed'),
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
    context = {
        'entity': thing,                   # <-- critical for rendering composite!
        'entity_type': 'thing',
        'sensors': ent['sensors'],
        'actors': ent['actors'],
        'actuators': ent['actuators']
    }

    m = build_entity_model(context)
    return m