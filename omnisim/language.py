from textx import language

from .lang import (
    get_actor_mm,
    get_datatype_mm,
    get_entity_mm,
    get_communication_mm,
    get_env_mm,
    get_thing_mm
)
@language('omnisim-actor', '*.actor')
def actor_language():
    "Omnisim Actor language"
    mm = get_actor_mm()
    return mm

@language('omnisim-dtype', '*.dtype')
def dtypes_language():
    "Omnisim DataType language"
    mm = get_datatype_mm()
    return mm

@language('omnisim-ent', '*.ent')
def entity_language():
    "Omnisim Entity language"
    mm = get_entity_mm()
    return mm

@language('omnisim-comm', '*.comm')
def communication_language():
    "Omnisim Communication language"
    mm = get_communication_mm()
    return mm

@language('omnisim-thing', '*.thing')
def thing_language():
    "Omnisim Thing language"
    mm = get_thing_mm()
    return mm

@language('omnisim-env', '*.env')
def env_language():
    "Omnisim Environment language"
    mm = get_env_mm()
    return mm