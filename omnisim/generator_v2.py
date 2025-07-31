from os import path, getcwd

from textx import GeneratorDesc
import jinja2

from .lang import build_model

_THIS_DIR = path.abspath(path.dirname(__file__))

# Initialize template engine.
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(path.join(_THIS_DIR, 'templates')),
    trim_blocks=True,
    lstrip_blocks=True
)
sensor_tpl = jinja_env.get_template('sensor.tpl')
actor_tpl = jinja_env.get_template('actor.tpl')

class GeneratorCommlibPy:
    srcgen_folder = path.realpath(getcwd())

    @staticmethod
    def generate(model_fpath: str,
                 gen_imports: bool = False,
                 out_dir: str = None):
        # Create output folder
        print("🚀 generate() called")
        if out_dir is None:
            out_dir = GeneratorCommlibPy.srcgen_folder
        model = build_model(model_fpath)

# # Check this again!!!
def _generator_commlib_py_impl(metamodel, model, output_path, overwrite,
                               debug, **custom_args):
    # Some code that perform generation
    gen_imports = custom_args['gen_imports'] if 'gen_imports' in custom_args \
        else True
    GeneratorCommlibPy.generate(model._tx_filename, gen_imports=gen_imports)

generator_commlib = GeneratorDesc(
    language='omnisim',
    target='python',
    description='Generate Python code for omnisim model',
    generator=_generator_commlib_py_impl)

# if __name__ == "__main__":
#     from sys import argv
#     if len(argv) < 3:
#         print("Usage: python -m omnisim.generator models/entities/MyEntities.ent models/communication/MyComms.comm")
#     else:
#         GeneratorCommlibPy.generate(argv[1], argv[2])