import click
import os
import math
from ..utils.utils import GENFILES_REPO_PATH

from ..lang import (
    build_model,
    preload_models,
    preload_dtype_models,
    # preload_thing_models,
    # preload_actor_models,
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
from ..transformations.node2vcode import model_to_vcode, env_to_vcode
from ..utils import validate_pose as vp

dtypes_output_dir = os.path.join(GENFILES_REPO_PATH, "datatypes")
comms_output_dir = os.path.join(GENFILES_REPO_PATH, "communications")
things_output_dir = os.path.join(GENFILES_REPO_PATH, "things")
actors_output_dir = os.path.join(GENFILES_REPO_PATH, "actors")
envs_output_dir   = os.path.join(GENFILES_REPO_PATH, "environments")
t2e_output_dir = r'C:\thesis\omnisim\generated_files'

@click.group("omnisim")
@click.pass_context
def cli(ctx):
   """An example CLI for interfacing with a document"""
   # pprint(ctx.obj)
   pass

# [*] How to run the cli:
# validate: python -m omnisim.cli.cli validate omnisim/models/things/
# t2e: python -m omnisim.cli.cli t2e omnisim/models/things/
# t2d: python -m omnisim.cli.cli t2d omnisim/models/things/
# t2c: python -m omnisim.cli.cli t2c omnisim/models/things/
# t2vc: python -m omnisim.cli.cli t2vc omnisim/models/things/
@cli.command("validate")
@click.argument("model_filepath")
@click.pass_context
def validate(_, model_filepath):
    print(f'[*] Running validation for model {model_filepath}')
    model = build_model(model_filepath)
    if model:
        print(f'[*] Validation passed!\n')

@cli.command("t2c")
@click.argument("model_file")
@click.pass_context
def t2c(_, model_file):
    try:
        print(f'[*] Executing Thing-to-Comms M2M...')
        model_filename = os.path.basename(model_file)
        # Only things have communication abilities so no need to check for actors
        if model_filename.endswith('.thing'):
            print(f'[*] Detected Thing model: {model_filename}')
            preload_dtype_models()
            thing_mm = get_thing_mm()
            tmodel = thing_mm.model_from_file(model_file)
            thing = tmodel.thing
            comms_model = node_to_comms_m2m(thing)
            basename = getattr(thing, "subtype", None)
            basename = basename.lower() if basename else thing.type.lower()
            filename = f'{basename}.comm'
        else:
            print(f'[X] Unsupported model file type: {model_filename}')
            raise ValueError()
        filepath = os.path.join(comms_output_dir, filename)
        # remove old dtype file if it exists
        if os.path.exists(filepath):
            os.remove(filepath)
        with open(filepath, 'w') as fp:
            fp.write(comms_model)
        print(f'[*] Stored Communications model in file: {filepath}')
        print(f'[*] Validating Communications model...')
        model = build_model(filepath)
        if model:
            print(f'[*] Validation passed!\n')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise

@cli.command("t2d")
@click.argument("model_file")
@click.pass_context
def t2d(_, model_file):
    try:
        print(f'[*] Executing Thing-to-Dtypes M2M...')
        model_filename = os.path.basename(model_file)

        # Check if it's an actor or thing file
        if model_filename.endswith('.actor'):
            print(f'[*] Detected Actor model: {model_filename}')
            preload_dtype_models()
            actor_mm = get_actor_mm()
            amodel = actor_mm.model_from_file(model_file)
            actor = amodel.actor  # Top-level is 'actor' in actor grammar
            dtypes_model = node_to_dtypes_m2m(actor)
            basename = getattr(actor, "subtype", None)
            basename = basename.lower() if basename else actor.type.lower()
            filename = f'{basename}.dtype'
        elif model_filename.endswith('.thing'):
            print(f'[*] Detected Thing model: {model_filename}')
            preload_dtype_models()
            thing_mm = get_thing_mm()
            tmodel = thing_mm.model_from_file(model_file)
            thing = tmodel.thing
            dtypes_model = node_to_dtypes_m2m(thing)
            basename = getattr(thing, "subtype", None)
            basename = basename.lower() if basename else thing.type.lower()
            filename = f'{basename}.dtype'
        else:
            print(f'[X] Unsupported model file type: {model_filename}')
            raise ValueError()
        
        filepath = os.path.join(dtypes_output_dir, filename)
        # remove old dtype file if it exists
        if os.path.exists(filepath):
            os.remove(filepath)
        with open(filepath, 'w') as fp:
            fp.write(dtypes_model)
        print(f'[*] Stored Data model in file: {filepath}')
        print(f'[*] Validating Data model...')
        model = build_model(filepath)
        if model:
            print(f'[*] Validation passed!\n')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise

@cli.command("t2e")
@click.argument("model_file")
@click.pass_context
def t2e(_, model_file):
    try:
        print(f'[*] Executing Thing-to-Entity M2M...')
        model_filename = os.path.basename(model_file)
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

        filepath = os.path.join(t2e_output_dir, filename)
        with open(filepath, 'w') as fp:
            fp.write(entity_model)
        print(f'[*] Generated output Entity model: {filepath}')
        print(f'[*] Validating Generated Entity Model...')
        model = build_model(filepath)
        if model:
            print(f'[*] Model validation succeded!\n')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise

@cli.command("t2vc")
@click.argument("model_file")
@click.pass_context
def t2vc(ctx, model_file):
    try:
        model_filename = os.path.basename(model_file).lower()
        model_kind = None

        # --- Detect model kind ---
        if model_filename.endswith('.thing'):
            print(f'[*] Detected Thing model: {model_filename}')
            mm = get_thing_mm()
            model = mm.model_from_file(model_file)
            obj = model.thing
            model_kind = "thing"
        elif model_filename.endswith('.actor'):
            print(f'[*] Detected Actor model: {model_filename}')
            mm = get_actor_mm()
            model = mm.model_from_file(model_file)
            obj = model.actor
            model_kind = "actor"
        elif model_filename.endswith('.env'):
            print(f'[*] Detected Environment model: {model_filename}')
            model = build_model(model_file)
            obj = model.environment
            model_kind = "environment"
        else:
            print("[X] Unknown model type (expected .thing, .actor, or .env)")
            return

        # --- Handle Environment separately ---
        if model_kind == "environment":
            # Load all .comm and .dtype
            comm_dir = os.path.join(GENFILES_REPO_PATH, "communications")
            dtype_dir = os.path.join(GENFILES_REPO_PATH, "datatypes")
            communication_mm = get_communication_mm()
            dtypes_mm = get_datatype_mm()

            comms = [
                communication_mm.model_from_file(os.path.join(comm_dir, f))
                for f in os.listdir(comm_dir) if f.endswith(".comm")
            ]
            dtypes = [
                dtypes_mm.model_from_file(os.path.join(dtype_dir, f))
                for f in os.listdir(dtype_dir) if f.endswith(".dtype")
            ]
            print(f'[*] Loaded all Communications and Data models for environment.')

            gen_code = env_to_vcode(obj, comms, dtypes)
            filename = f"{obj.name.lower()}.py"
            outdir = envs_output_dir

        else:
            # --- Handle Thing / Actor (atomic or composite) ---
            obj_class = getattr(obj, "class", "").lower()
            obj_type = getattr(obj, "type", "").lower()
            obj_subtype = getattr(obj, "subtype", "").lower()
            obj_name = obj_subtype or obj_type or obj.__class__.__name__.lower()

            communication_mm = get_communication_mm()
            dtypes_mm = get_datatype_mm()

            comms_model_file = None
            comms = None

            # --- Communication model resolution ---
            comms_dir = os.path.join(GENFILES_REPO_PATH, "communications")

            # Try subtype first (Camera → camera.comm)
            candidate_paths = [
                os.path.join(comms_dir, f"{obj_subtype}.comm"),
                os.path.join(comms_dir, f"{obj_type}.comm"),
            ]

            for path in candidate_paths:
                if path and os.path.exists(path):
                    comms_model_file = path
                    break

            if comms_model_file:
                comms = communication_mm.model_from_file(comms_model_file)
                print(f'[*] Loaded Communications model from file: {comms_model_file}')
            else:
                print("[!] No communications file found (this may be fine for actuators or composites).")

            # --- DataType resolution ---
            dtypes_model_file = None
            dtype_dir = os.path.join(GENFILES_REPO_PATH, "datatypes")
            for name in [obj_subtype, obj_type]:
                if name:
                    candidate = os.path.join(dtype_dir, f"{name}.dtype")
                    if os.path.exists(candidate):
                        dtypes_model_file = candidate
                        break

            if dtypes_model_file:
                dtypes = dtypes_mm.model_from_file(dtypes_model_file)
                print(f'[*] Loaded Data model from file: {dtypes_model_file}')
            else:
                raise FileNotFoundError(f"No matching .dtype file for {obj_name}")

            # --- Code generation ---
            if obj_class == "sensor" or obj.__class__.__name__.lower() in ["compositething", "robot"]:
                gen_code = model_to_vcode(obj, comms, dtypes)
            else:
                gen_code = model_to_vcode(obj, comms=None, dtypes=dtypes)

            filename = f"{obj_name}.py"
            outdir = actors_output_dir if model_kind == "actor" else things_output_dir

        # --- Write generated file ---
        filepath = os.path.join(outdir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        with open(filepath, "w") as fp:
            fp.write(gen_code)

        print(f"[*] Code generation succeeded! File: {filepath}\n")

    except Exception as e:
        print(f"[X] Transformation failed: {e}")
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
        # preload_dtype_models()
        # preload_thing_models()
        # preload_actor_models()
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