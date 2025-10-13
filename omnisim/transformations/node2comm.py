import jinja2
import os
from ..utils.utils import TEMPLATES_PATH, GENFILES_REPO_PATH
from ..lang import (
    build_model,
    preload_models,
    preload_dtype_models,
    get_datatype_mm
)
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    extensions=['jinja2.ext.do'],
    trim_blocks=True,
    lstrip_blocks=True
)

comms_tpl = jinja_env.get_template('t2c.jinja')

def build_comms_model(obj, dtype=None) -> str:
    context = {
        'thing': obj if obj.__class__.__name__.lower() != "thing" else None,
        'actor': obj if obj.__class__.__name__.lower() == "actor" else None,
        "dtype": dtype,
    }
    modelf = comms_tpl.render(context)
    return modelf

def log_node_info(model):
    components = []

    print(f'[*] Model: {model.type} ({model.__class__.__name__})')

    # Sensors
    if hasattr(model, 'sensors'):
        print(f'[*] Installed sensors:')
        for posed_sensor in model.sensors:
            sensor = posed_sensor.ref
            print(f'    - {sensor.subtype}: ({sensor.__class__.__name__})')
            components.append((sensor, getattr(posed_sensor, 'name', sensor.name)))

    # Actuators
    if hasattr(model, 'actuators'):
        print(f'[*] Installed actuators:')
        for posed_actuator in model.actuators:
            actuator = posed_actuator.ref
            print(f'    - {actuator.subtype}: ({actuator.__class__.__name__})')
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
        subtype = getattr(model, 'subtype', getattr(model, 'type', 'Unknown'))
        print(f'[*] Atomic: {subtype} ({model.__class__.__name__})')
        components.append((model, model.name))

    return components

def node_to_comms_m2m(thing) -> str:
    log_node_info(thing)
    # Load dtype if it exists
    dtype = None
    try:
        # Determine base name for dtype lookup (works for atomic and composite)
        dtype_base = getattr(thing, "subtype", None) or getattr(thing, "type", None) or thing.__class__.__name__
        dtype_filename = f"{dtype_base.lower()}.dtype"
        dtype_path = os.path.join(GENFILES_REPO_PATH, "datatypes", dtype_filename)

        if os.path.exists(dtype_path):
            dtypes_mm = get_datatype_mm()
            dtype_model = dtypes_mm.model_from_file(dtype_path)
            # each .dtype file has at least one DataType
            dtype = dtype_model.types[0]
            print(f"[*] Using dtype model: {dtype_path}")
        else:
            print(f"[!] No dtype file found for {thing.subtype}, skipping extra properties")
    except Exception as e:
        thing_name = getattr(thing, "name", getattr(thing, "type", thing.__class__.__name__))
        print(f"[X] Failed to load dtype for {thing_name}: {e}")

    # Render comms
    cmodel_str = build_comms_model(thing, dtype)
    return cmodel_str