import click
from pprint import pprint
from os import path, getcwd

from ..lang import build_model, preload_thing_models, preload_dtype_models
from ..lang import get_actor_mm, get_thing_mm, get_communication_mm

from ..transformations.thing2entity import thing_to_entity_m2m
from ..transformations.actor2entity import actor_to_entity_m2m
from ..transformations.thing2vcode import thing_to_vcode

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
# t2vc: python -m omnisim.cli.cli t2vc omnisim/models/things/sonar.thing omnisim/models/communication/omms.comm
@cli.command("validate")
@click.argument("model_filepath")
@click.pass_context
def validate(_, model_filepath):
    print(f'[*] Running validation for model {model_filepath}')
    model = build_model(model_filepath)
    if model:
        print(f'[*] Validation passed!')

@cli.command("t2e")
@click.argument("model_file")
@click.pass_context
def t2e(_, model_file):
    try:
        print(f'[*] Executing Thing-to-Entity M2M...')
        model_filename = path.basename(model_file)
        # if not model_filename.endswith('.thing'):
        #     print(f'[X] Not a thing model.')
        #     raise ValueError()
        # Check if it's an actor or thing file
        if model_filename.endswith('.actor'):
            print(f'[*] Detected Actor model: {model_filename}')
            preload_dtype_models()
            actor_mm = get_actor_mm()
            amodel = actor_mm.model_from_file(model_file)
            actor = amodel.actor  # Top-level is 'actor' in actor grammar
            entity_model = actor_to_entity_m2m(actor)
            filename = f'{actor.name}.ent'
        elif model_filename.endswith('.thing'):
            print(f'[*] Detected Thing model: {model_filename}')
            preload_thing_models()
            thing_mm = get_thing_mm()
            tmodel = thing_mm.model_from_file(model_file)
            thing = tmodel.thing
            entity_model = thing_to_entity_m2m(thing)
            filename = f'{thing.name}.ent'
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
@click.pass_context
def t2vc(_, model_file, comms_model_file):
    try:
        model_filename = path.basename(model_file)
        if not model_filename.endswith('.thing'):
            print(f'[X] Not a thing model.')
            raise ValueError()
        preload_thing_models()
        thing_mm = get_thing_mm()
        tmodel = thing_mm.model_from_file(model_file)
        thing = tmodel.thing

        communication_mm = get_communication_mm()
        communication_model = communication_mm.model_from_file(comms_model_file)
        comms = communication_model
        gen_code = thing_to_vcode(thing, comms)

        filename = f'{thing.name}.py'
        filepath = path.join(t2vc_output_dir, filename)
        with open(filepath, 'w') as fp:
            fp.write(gen_code)

        print(f'[*] Code generation succeded! You can find it in {filepath} file')
    except Exception as e:
        print(f'[X] Transformation failed: {e}')
        raise


def main():
   cli(prog_name="omnisim")


if __name__ == '__main__':
   main()