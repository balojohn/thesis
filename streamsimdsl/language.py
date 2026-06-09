from textx import language

from .lang import (
    get_actor_mm,
    get_datatype_mm,
    get_entity_mm,
    get_communication_mm,
    get_env_mm,
    get_thing_mm
)
@language('streamsimdsl-actor', '*.actor')
def actor_language():
    "streamsimdsl Actor language"
    mm = get_actor_mm()
    return mm

@language('streamsimdsl-dtype', '*.dtype')
def dtypes_language():
    "streamsimdsl DataType language"
    mm = get_datatype_mm()
    return mm

@language('streamsimdsl-ent', '*.ent')
def entity_language():
    "streamsimdsl Entity language"
    mm = get_entity_mm()
    return mm

@language('streamsimdsl-comm', '*.comm')
def communication_language():
    "streamsimdsl Communication language"
    mm = get_communication_mm()
    return mm

@language('streamsimdsl-thing', '*.thing')
def thing_language():
    "streamsimdsl Thing language"
    mm = get_thing_mm()
    return mm

@language('streamsimdsl-env', '*.env')
def env_language():
    "streamsimdsl Environment language"
    mm = get_env_mm()
    return mm