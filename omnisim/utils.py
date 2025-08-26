from os.path import dirname, join
import math
import random

THIS_DIR = dirname(__file__)
MODEL_REPO_PATH = join(THIS_DIR, 'models')
TEMPLATES_PATH = join(THIS_DIR, 'templates')

def log_thing_info(thing):
    components = []

    print(f'[*] Thing model: {thing.name}')
    if hasattr(thing, 'sensors') and hasattr(thing, 'actors') and hasattr(thing, 'actuators'):
        print(f'[*] Installed sensors:')
        for posed_sensor in thing.sensors:
            sensor = posed_sensor.ref
            print(f'    - {sensor.name}: ({sensor.__class__.__name__})')
            components.append((sensor, posed_sensor.name))
        # print(f'[*] Installed actors:')
        # for posed_actor in thing.actors:
        #     actor = posed_actor.ref
        #     print(f'    - {actor.name}: ({actor.__class__.__name__})')
        #     components.append((actor, posed_actor.name))
        print(f'[*] Installed actuators:')
        for posed_actuator in thing.actuators:
            actuator = posed_actuator.ref
            print(f'    - {actuator.name}: ({actuator.__class__.__name__})')
            components.append((actuator, posed_actuator.name))
        # if thing.__class__.__name__ == 'Robot':
        #     print(f'[*] Installed Computation Boards:')
        #     for posed_board in thing.boards:
        #         board = posed_board.ref
        #         print(f'- {board}')
    else:
        # Atomic thing
        print(f'[*] Atomic Thing: {thing.name} ({thing.__class__.__name__})')
        components.append((thing, thing.name))

    return components

class Dispersion:
    def __init__(self, type_name: str, **params):
        self.type_name = type_name
        self.params = params

    def apply(self, x: float) -> float:
        if self.type_name == "Constant":
            return x + self.params.get("value", 0.0)
        elif self.type_name == "Linear":
            start = self.params.get("startingPoint", 0.0)
            step = self.params.get("step", 1.0)
            return start + step * x
        elif self.type_name == "Quadratic":
            a = self.params.get("a", 0.0)
            b = self.params.get("b", 0.0)
            c = self.params.get("c", 0.0)
            return a * x**2 + b * x + c
        elif self.type_name == "Exponential":
            base = self.params.get("base", math.e)
            y_int = self.params.get("yIntercept", 0.0)
            return y_int + base ** x
        elif self.type_name == "Logarithmic":
            base = self.params.get("base", math.e)
            alpha = self.params.get("alpha", 1.0)
            return alpha * math.log(x + 1, base)
        else:
            raise ValueError(f"Unknown dispersion type: {self.type_name}")
