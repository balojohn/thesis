from os import path, getcwd

from textx import GeneratorDesc
import jinja2

from dummy.lang.utils import build_model

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
    def generate(entity_model_fpath: str,
                 comm_model_fpath: str,
                 gen_imports: bool = False,
                 out_dir: str = None):
        # Create output folder
        print("🚀 generate() called")
        if out_dir is None:
            out_dir = GeneratorCommlibPy.srcgen_folder
        
        entity_model = build_model(entity_model_fpath)
        comm_model = build_model(comm_model_fpath)
        
        # print("🚀 comm_model called")
        # Collect sensor/actor entities
        sensors = [e for e in entity_model.entities if e.etype.lower() == "sensor"]
        actors = [e for e in entity_model.entities if e.etype.lower() == "actor"]

        # Find endpoints
        publishers = [pubs for pubs in comm_model.endpoints if pubs.__class__.__name__.lower() == "publisher"]
        subscribers = [subs for subs in comm_model.endpoints if subs.__class__.__name__.lower() == "subscriber"]
        
        # Match sensor → subscriber, actor → publisher
        sensor_entity = next((s for s in sensors if any(sub.uri == s.topic for sub in subscribers)), None)
        actor_entity = next((a for a in actors if any(pub.uri == a.topic for pub in publishers)), None)

        # Find the message used by both
        sensor_ep = next((sub for sub in subscribers if sub.uri == sensor_entity.topic), None)
        # print(f"[{sensor_entity}]: {sensor_ep.msg}")
        # actor_ep = next((pub for pub in publishers if pub.uri == actor_entity.topic), None)
        # print(f"[{actor_entity}]: {actor_ep.msg}")
        # print(f"{sensor_ep.msg.properties}")
        # print(f"{actor_ep.msg.properties}")
        message = next((m for m in comm_model.msgs if m.name == sensor_ep.msg.name), None)
        # print(f"Message: {message}")

        sensor_template_data = {
            'message_name': message.name,
            'message_properties': message.properties,
            'sensor_name': sensor_entity.name,
            'sensor_id': sensor_entity.name,
            'sensor_type': sensor_entity.etype,
            'sensor_topic': actor_entity.topic,
            'pub_freq': 1,
        }

        actor_template_data = {
            'message_name': message.name,
            'message_properties': message.properties,
            'actor_name': actor_entity.name,
            'actor_id': actor_entity.name,
            'actor_type': actor_entity.etype,
            'actor_topic': actor_entity.topic
        }

        sensor_rendered_code = sensor_tpl.render(**sensor_template_data)
        actor_rendered_code = actor_tpl.render(**actor_template_data)
        sfilename = f"{sensor_entity.name}.py"
        sfilepath = path.join(out_dir, sfilename)

        with open(sfilepath, 'w') as f:
            f.write(sensor_rendered_code)

        print(f"✅ Generated: {sfilepath}")

        afilename = f"{actor_entity.name}.py"
        afilepath = path.join(out_dir, afilename)

        with open(afilepath, 'w') as f:
            f.write(actor_rendered_code)

        print(f"✅ Generated: {afilepath}")

# # Check this again!!!
def _generator_commlib_py_impl(metamodel, model, output_path, overwrite,
                               debug, **custom_args):
    # Some code that perform generation
    gen_imports = custom_args['gen_imports'] if 'gen_imports' in custom_args \
        else True
    GeneratorCommlibPy.generate(model._tx_filename, gen_imports=gen_imports)

generator_commlib = GeneratorDesc(
    language='dummy-ent',
    target='python',
    description='Generate Python code for Dummy model',
    generator=_generator_commlib_py_impl)

if __name__ == "__main__":
    from sys import argv
    if len(argv) < 3:
        print("Usage: python -m dummy.generator models/entities/entities.ent models/communication/communications.comm")
    else:
        GeneratorCommlibPy.generate(argv[1], argv[2])