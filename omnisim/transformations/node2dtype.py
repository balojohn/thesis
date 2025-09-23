import jinja2

from ..utils.utils import TEMPLATES_PATH
from ..lang import build_model

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    extensions=['jinja2.ext.do'],
    trim_blocks=True,
    lstrip_blocks=True
)

dtypes_tpl = jinja_env.get_template('t2d.jinja')

def build_dtypes_model(obj) -> str:
    cls = obj.__class__.__name__.lower()
    context = {
        'thing': obj if cls != "actor" else None,
        'actor': obj if cls == "actor" else None,
    }
    modelf = dtypes_tpl.render(context)
    return modelf

def log_node_info(model):
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
            components.extend(log_node_info(cthing))

    # Atomic fallback
    if not (hasattr(model, 'sensors') or hasattr(model, 'actuators') or hasattr(model, 'composites')):
        print(f'[*] Atomic: {model.name} ({model.__class__.__name__})')
        components.append((model, model.name))

    return components

def node_to_dtypes_m2m(obj) -> str:
    log_node_info(obj)
    dmodel_str = build_dtypes_model(obj)
    return dmodel_str