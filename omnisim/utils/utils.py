from os.path import dirname, join
import time, math, random

THIS_DIR = dirname((dirname(__file__)))
MODEL_REPO_PATH = join(THIS_DIR, 'models')
GENFILES_REPO_PATH = join(THIS_DIR, 'generated_files')
TEMPLATES_PATH = join(THIS_DIR, 'templates')

def apply_dispersion(x: float, type_name: str, **params) -> float:
    if type_name == "Constant":
        return x + params.get("value", 0.0)
    elif type_name == "Linear":
        start = params.get("startingPoint", 0.0)
        step = params.get("step", 1.0)
        return start + step * x
    elif type_name == "Quadratic":
        a = params.get("a", 0.0)
        b = params.get("b", 0.0)
        c = params.get("c", 0.0)
        return a * x**2 + b * x + c
    elif type_name == "Exponential":
        base = params.get("base", math.e)
        y_int = params.get("yIntercept", 0.0)
        return y_int + base ** x
    elif type_name == "Logarithmic":
        base = params.get("base", math.e)
        alpha = params.get("alpha", 1.0)
        return alpha * math.log(x + 1, base)
    else:
        raise ValueError(f"Unknown dispersion type: {type_name}")

def apply_noise(value: float, noise: dict) -> float:
    """
    Applies a noise model to a base value.

    Parameters
    ----------
    value : float
        The clean (true) sensor value before noise.
    noise : dict
        A dictionary describing the noise type and parameters, e.g.:
        {"type": "Gaussian", "mean": 0.0, "std": 1.5}
        {"type": "Uniform", "min": -1.0, "max": 1.0}
        {"type": "CustomNoise", "type": "sine", "params": {"amp":1.0,"freq":2.0}}

    Returns
    -------
    float
        The noisy value.
    """
    if not isinstance(noise, dict):
        return value

    ntype = noise.get("type", "").capitalize()

    # === Gaussian(mean, std) ===
    if ntype == "Gaussian":
        mean = noise.get("mean", 0.0)
        std = noise.get("std", 0.0)
        return value + random.gauss(mean, std)

    # === Uniform(min, max) ===
    elif ntype == "Uniform":
        nmin = noise.get("min", 0.0)
        nmax = noise.get("max", 0.0)
        return value + random.uniform(nmin, nmax)

    # === CustomNoise(type, params) ===
    elif ntype == "Customnoise":
        ctype = noise.get("type", "").lower()
        params = noise.get("params", {})

        # Example extension for common custom types
        if ctype == "sine":
            amp = params.get("amp", 1.0)
            freq = params.get("freq", 1.0)
            t = time.monotonic()
            return value + amp * math.sin(freq * t)
        elif ctype == "step":
            step = params.get("step", 1.0)
            return value + (random.choice([-1, 1]) * step)
        else:
            # Unknown custom model — return unchanged
            return value

    # === Fallback ===
    return value