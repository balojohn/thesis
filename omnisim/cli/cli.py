import click
from os import path
import math

from ..lang import (
    build_model,
    preload_dtype_models,
    preload_thing_models,
    preload_actor_models,
    get_actor_mm,
    get_thing_mm,
    get_env_mm,
    get_communication_mm,
    get_datatype_mm,
    get_env_mm
)
from ..transformations.thing2entity import thing_to_entity_m2m
from ..transformations.actor2entity import actor_to_entity_m2m
from ..transformations.node2comm import node_to_comms_m2m
from ..transformations.node2dtype import node_to_dtypes_m2m
from ..transformations.node2vcode import model_to_vcode, env_to_vcode, composite_to_vcode
from ..utils import validate_pose as vp

dtypes_output_dir = r'C:\thesis\omnisim\generated_files/datatypes'
comms_output_dir = r'C:\thesis\omnisim\generated_files/communications'
things_output_dir = r'C:\thesis\omnisim\generated_files/things'
actors_output_dir = r'C:\thesis\omnisim\generated_files/actors'
t2e_output_dir = r'C:\thesis\omnisim\generated_files'
t2vc_output_dir = r'C:\thesis\omnisim\generated_files'

@click.group("omnisim")
@click.pass_context
def cli(ctx):
   """An example CLI for interfacing with a document"""
   # pprint(ctx.obj)
   pass

# [*] How to run the cli:
# validate: python -m omnisim.cli.cli validate omnisim/models/modelyouwant
# t2e: python -m omnisim.cli.cli t2e omnisim/models
# t2vc: python -m omnisim.cli.cli t2vc omnisim/models/things/sonar.thing omnisim/models/communication/mycomms.comm omnisim/models/datatypes/sensors.dtype
# validate-pose: python -m omnisim.cli.cli validate-pose omnisim/models/environment/myenv.env
@cli.command("validate")
@click.argument("model_filepath")
@click.pass_context
def validate(_, model_filepath):
    print(f'[*] Running validation for model {model_filepath}')
    model = build_model(model_filepath)
    if model:
        print(f'[*] Validation passed!')

@cli.command("t2c")
@click.argument("model_file")
@click.pass_context
def t2c(_, model_file):
    try:
        print(f'[*] Executing Thing-to-Comms M2M...')
        model_filename = path.basename(model_file)
        # Check if it's an actor or thing file
        if model_filename.endswith('.actor'):
            print(f'[*] Detected Actor model: {model_filename}')
            preload_dtype_models()
            actor_mm = get_actor_mm()
            amodel = actor_mm.model_from_file(model_file)
            actor = amodel.actor  # Top-level is 'actor' in actor grammar
            comms_model = node_to_comms_m2m(actor)
            filename = f'{actor.name.lower()}.comm'
        elif model_filename.endswith('.thing'):
            print(f'[*] Detected Thing model: {model_filename}')
            preload_dtype_models()
            thing_mm = get_thing_mm()
            tmodel = thing_mm.model_from_file(model_file)
            thing = tmodel.thing
            comms_model = node_to_comms_m2m(thing)
            filename = f'{thing.name.lower()}.comm'
        else:
            print(f'[X] Unsupported model file type: {model_filename}')
            raise ValueError()
        filepath = path.join(comms_output_dir, filename)
        with open(filepath, 'w') as fp:
            fp.write(comms_model)
        print(f'[*] Stored Communications model in file: {filepath}')
        print(f'[*] Validating Communications model...')
        model = build_model(filepath)
        if model:
            print(f'[*] Validation passed!')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise

@cli.command("t2d")
@click.argument("model_file")
@click.pass_context
def t2d(_, model_file):
    try:
        print(f'[*] Executing Thing-to-Dtypes M2M...')
        model_filename = path.basename(model_file)
        # Check if it's an actor or thing file
        if model_filename.endswith('.actor'):
            print(f'[*] Detected Actor model: {model_filename}')
            preload_dtype_models()
            actor_mm = get_actor_mm()
            amodel = actor_mm.model_from_file(model_file)
            actor = amodel.actor  # Top-level is 'actor' in actor grammar
            dtypes_model = node_to_dtypes_m2m(actor)
            filename = f'{actor.name.lower()}.comm'
        elif model_filename.endswith('.thing'):
            print(f'[*] Detected Thing model: {model_filename}')
            preload_dtype_models()
            thing_mm = get_thing_mm()
            tmodel = thing_mm.model_from_file(model_file)
            thing = tmodel.thing
            dtypes_model = node_to_dtypes_m2m(thing)
            filename = f'{thing.name.lower()}.dtype'
        else:
            print(f'[X] Unsupported model file type: {model_filename}')
            raise ValueError()
        filepath = path.join(dtypes_output_dir, filename)
        with open(filepath, 'w') as fp:
            fp.write(dtypes_model)
        print(f'[*] Stored Data model in file: {filepath}')
        print(f'[*] Validating Data model...')
        model = build_model(filepath)
        if model:
            print(f'[*] Validation passed!')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise

@cli.command("t2e")
@click.argument("model_file")
@click.pass_context
def t2e(_, model_file):
    try:
        print(f'[*] Executing Thing-to-Entity M2M...')
        model_filename = path.basename(model_file)
        # Check if it's an actor or thing file
        if model_filename.endswith('.actor'):
            print(f'[*] Detected Actor model: {model_filename}')
            preload_dtype_models()
            actor_mm = get_actor_mm()
            amodel = actor_mm.model_from_file(model_file)
            actor = amodel.actor  # Top-level is 'actor' in actor grammar
            entity_model = actor_to_entity_m2m(actor)
            filename = f'{actor.name.lower()}.ent'
        elif model_filename.endswith('.thing'):
            print(f'[*] Detected Thing model: {model_filename}')
            preload_dtype_models()
            thing_mm = get_thing_mm()
            tmodel = thing_mm.model_from_file(model_file)
            thing = tmodel.thing
            entity_model = thing_to_entity_m2m(thing)
            filename = f'{thing.name.lower()}.ent'
        else:
            print(f'[X] Unsupported model file type: {model_filename}')
            raise ValueError()

        filepath = path.join(t2e_output_dir, filename)
        with open(filepath, 'w') as fp:
            fp.write(entity_model)
        print(f'[*] Generated output Entity model: {filepath}')
        print(f'[*] Validating Generated Entity Model...')
        model = build_model(filepath)
        if model:
            print(f'[*] Model validation succeded!')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise

@cli.command("t2vc")
@click.argument("model_file")
@click.argument("comms_model_file")
@click.argument("dtypes_model_file")
@click.pass_context
def t2vc(ctx, model_file, comms_model_file, dtypes_model_file):
    try:
        preload_dtype_models()
        dtypes_mm = get_datatype_mm()
        dtypes = dtypes_mm.model_from_file(dtypes_model_file)

        model_filename = path.basename(model_file).lower()
        # Choose metamodel based on file extension or content
        if model_filename.endswith('.thing'):
            mm = get_thing_mm()
            model = mm.model_from_file(model_file)
            obj = model.thing
            obj_type = obj.__class__.__name__.lower()
            model_kind = "thing"
        elif model_filename.endswith('.actor'):
            mm = get_actor_mm()
            model = mm.model_from_file(model_file)
            obj = model.actor
            obj_type = obj.__class__.__name__.lower()
            model_kind = "actor"
        elif model_filename.endswith(".env"):
            preload_thing_models()
            preload_actor_models()
            mm = get_env_mm()
            model = mm.model_from_file(model_file)
            obj = model.environment
            model_kind = "environment"
        else:
            print("[X] Unknown model type (expected .thing, .actor, or .env)")
            return

        # Parse communications
        communication_mm = get_communication_mm()
        comms = communication_mm.model_from_file(comms_model_file)
        
        # Generate code
        if model_kind == "environment":
            gen_code = env_to_vcode(obj, comms, dtypes)  # uses environment_node.tpl
            filename = f"{obj.name.lower()}_env.py"
        elif obj_type in ["compositething", "robot"]:
            gen_code = composite_to_vcode(obj, comms, dtypes)
            filename = f"{obj.name.lower()}.py"
        else:
            gen_code = model_to_vcode(obj, comms, dtypes)  # uses node.tpl
            filename = f"{obj.name.lower()}.py"

        filename = f'{obj.name.lower()}.py'
        filepath = path.join(things_output_dir, filename)
        with open(filepath, 'w') as fp:
            fp.write(gen_code)

        print(f'[*] Code generation succeded! You can find it in {filepath} file')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise

@cli.command("validate-pose")
# @click.argument("thing_model_file")
@click.argument("env_model_file")
def validate_pose(env_model_file):
    """
    Validates that all poses are within the environment's grid.
    """
    try:
        print(f'[*] Running validate-pose for environment {env_model_file}')

        # Load environment
        preload_dtype_models()
        preload_thing_models()
        preload_actor_models()
        env_mm = get_env_mm()
        envmodel = env_mm.model_from_file(env_model_file)
        env = envmodel.environment
        dims = env.grid[0]
        width, height = dims.width, dims.height
 
        if hasattr(env, 'things'):
            print('[*] Validating things...')
            vp.validate_entity_poses(env.things, width, height, "Thing")

        if hasattr(env, 'actors'):
            print('[*] Validating actors...')
            vp.validate_entity_poses(env.actors, width, height, "Actor")

        if hasattr(env, 'obstacles'):
            print('[*] Validating obstacles...')
            vp.validate_entity_poses(env.obstacles, width, height, "Obstacle")
    
    except Exception as e:
        print(f'[X] Validation failed: {e}')

def main():
   cli(prog_name="omnisim")


if __name__ == '__main__':
   main()