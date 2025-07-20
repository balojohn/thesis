import click
from pprint import pprint
from os.path import basename

from ..lang import build_model
from ..lang import get_thing_mm

# from ..transformations.thing2entity import thing_to_entity_m2m

@click.group("omnisim")
@click.pass_context
def cli(ctx):
   """An example CLI for interfacing with a document"""
   # pprint(ctx.obj)
   pass


@cli.command("validate")
@click.argument("model_filepath")
@click.pass_context
def validate(_, model_filepath):
    print(f'[*] Running validation for model {model_filepath}')
    model = build_model(model_filepath)
    if model:
        print(f'[*] Validation passed!')

# @cli.command("t2e")
# @click.argument("model_file")
# @click.pass_context
# def t2e(_, model_file):
#     print(f'[*] Executing Thing-to-Entity M2M...')
#     model_filename = basename(model_file)
#     if not model_filename.endswith('.thing'):
#         print(f'[X] Not a thing model.')
#         raise ValueError()
#     thing_mm = get_thing_mm()
#     tmodel = thing_mm.model_from_file(model_file)
#     thing = tmodel.thing
#     entity_model = thing_to_entity_m2m(thing)
#     filepath = f'{thing.name}.ent'
#     with open(filepath, 'w') as fp:
#         fp.write(entity_model)
#     print(f'[*] Generated output Entity model: {filepath}')
#     print(f'[*] Validating Generated Entity Model...')
#     model = build_model(filepath)
#     if model:
#         print(f'[*] Model validation succeded!')


# @cli.command("t2vc")
# @click.argument("model_file")
# @click.pass_context
# def t2vc(ctx, model_file):
#     model_filename = basename(model_file)
#     if not model_filename.endswith('.thing'):
#         print(f'[X] Not a thing model.')
#         raise ValueError()
#     thing_mm = get_thing_mm()
#     tmodel = thing_mm.model_from_file(model_file)
#     thing = tmodel.thing
#     a = thing_to_vcode(thing)

#     filepath = f'{thing.name}.py'
#     with open(filepath, 'w') as fp:
#         fp.write(a)

def main():
   cli(prog_name="omnisim")


if __name__ == '__main__':
   main()