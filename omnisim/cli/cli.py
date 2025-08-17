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
    get_communication_mm,
    get_datatype_mm,
    get_env_mm
)
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
@click.argument("thing_model_file")
@click.argument("comms_model_file")
@click.argument("dtypes_model_file")
@click.pass_context
def t2vc(_, thing_model_file, comms_model_file, dtypes_model_file):
    try:
        model_filename = path.basename(thing_model_file)
        if not model_filename.endswith('.thing'):
            print(f'[X] Not a thing model.')
            raise ValueError()
        preload_dtype_models()
        dtypes_mm = get_datatype_mm()
        dtypes = dtypes_mm.model_from_file(dtypes_model_file)
        thing_mm = get_thing_mm()
        tmodel = thing_mm.model_from_file(thing_model_file)
        thing = tmodel.thing
        communication_mm = get_communication_mm()
        comms = communication_mm.model_from_file(comms_model_file)
        
        gen_code = thing_to_vcode(thing, comms, dtypes)

        filename = f'{thing.name.lower()}.py'
        filepath = path.join(t2vc_output_dir, filename)
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

        def rotate_point(x, y, cx, cy, angle_deg):
            angle_rad = math.radians(angle_deg)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            dx = x - cx
            dy = y - cy
            x_new = cx + dx * cos_a - dy * sin_a
            y_new = cy + dx * sin_a + dy * cos_a
            return x_new, y_new 

        def get_bbox(shape, pose):
            cx = pose.translation.x
            cy = pose.translation.y
            yaw = pose.rotation.yaw if hasattr(pose.rotation, 'yaw') else 0

            points = []

            if shape.__class__.__name__ == 'Circle':
                r = shape.radius
                # Four extreme points
                raw_points = [
                    (cx - r, cy),
                    (cx + r, cy),
                    (cx, cy - r),
                    (cx, cy + r)
                ]
                points = [rotate_point(x, y, cx, cy, yaw) for x, y in raw_points]

            elif shape.__class__.__name__ == 'Square':
                l = shape.length
                half = l / 2
                raw_points = [
                    (cx - half, cy - half),
                    (cx + half, cy - half),
                    (cx + half, cy + half),
                    (cx - half, cy + half)
                ]
                points = [rotate_point(x, y, cx, cy, yaw) for x, y in raw_points]

            elif shape.__class__.__name__ == 'Rectangle':
                w, h = shape.width, shape.length
                hw = w / 2
                hh = h / 2
                raw_points = [
                    (cx - hw, cy - hh),
                    (cx + hw, cy - hh),
                    (cx + hw, cy + hh),
                    (cx - hw, cy + hh)
                ]
                points = [rotate_point(x, y, cx, cy, yaw) for x, y in raw_points]

            elif shape.__class__.__name__ == 'Cylinder':
                r = shape.radius
                raw_points = [
                    (cx - r, cy),
                    (cx + r, cy),
                    (cx, cy - r),
                    (cx, cy + r)
                ]
                points = [rotate_point(x, y, cx, cy, yaw) for x, y in raw_points]

            elif shape.__class__.__name__ == 'ArbitraryShape':
                raw_points = [(cx + p.x, cy + p.y) for p in shape.points]
                points = [rotate_point(x, y, cx, cy, yaw) for x, y in raw_points]

            elif shape.__class__.__name__ == 'ComplexShape':
                for subshape in shape.shapes:
                    sub_points = get_bbox(subshape, pose)  # recursively collect points
                    if isinstance(sub_points[0], tuple):  # raw points list
                        points.extend(sub_points)
                    else:  # nested min_x, min_y, max_x, max_y
                        min_x, min_y, max_x, max_y = sub_points
                        points.extend([(min_x, min_y), (max_x, max_y)])

            else:
                raise NotImplementedError(f"BBox not implemented for {shape.__class__.__name__}")

            xs = [x for x, _ in points]
            ys = [y for _, y in points]

            return (min(xs), min(ys), max(xs), max(ys))
        
        def is_within_bounds(pose, shape, env_width, env_height):
            min_x, min_y, max_x, max_y = get_bbox(shape, pose)
            return (0 <= min_x <= env_width and
                    0 <= max_x <= env_width and
                    0 <= min_y <= env_height and
                    0 <= max_y <= env_height)
        
        def validate_entity_poses(entities, env_width, env_height, entity_type="Entity"):
            for placement in entities:
                pose = placement.pose
                shape = placement.ref.shape
                name = placement.ref.name

                try:
                    inside = is_within_bounds(pose, shape, env_width, env_height)
                except NotImplementedError as e:
                    print(f"[?] {entity_type} '{name}' shape check skipped: {e}")
                    continue

                x, y = pose.translation.x, pose.translation.y
                
                # Build detailed shape description with dimensions
                if shape.__class__.__name__ == "Rectangle":
                    shape_desc = f"Rectangle(width={shape.width}, length={shape.length})"
                elif shape.__class__.__name__ == "Circle":
                    shape_desc = f"Circle(radius={shape.radius})"
                elif shape.__class__.__name__ == "Square":
                    shape_desc = f"Square(length={shape.length})"
                elif shape.__class__.__name__ == "Cylinder":
                    shape_desc = f"Cylinder(radius={shape.radius}, height={shape.height})"
                else:
                    shape_desc = shape.__class__.__name__

                tag = f"{entity_type} '{name}' at ({x}, {y}) with shape {shape_desc}"

                if inside:
                    print(f"[✓] {tag} is within bounds.")
                else:
                    print(f"[X] {tag} is OUTSIDE bounds ({env_width} x {env_height})")               
        
        if hasattr(env, 'things'):
            print('[*] Validating things...')
            validate_entity_poses(env.things, width, height, "Thing")

        if hasattr(env, 'actors'):
            print('[*] Validating actors...')
            validate_entity_poses(env.actors, width, height, "Actor")

        if hasattr(env, 'obstacles'):
            print('[*] Validating obstacles...')
            validate_entity_poses(env.obstacles, width, height, "Obstacle")
    
    except Exception as e:
        print(f'[X] Validation failed: {e}')

def main():
   cli(prog_name="omnisim")


if __name__ == '__main__':
   main()