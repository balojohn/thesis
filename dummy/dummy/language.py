from textx import language

from dummy.lang import (
    get_datatype_mm,
    get_entity_mm,
    get_communication_mm
)

@language('cpsml-dtype', '*.dtype')
def dtypes_language():
    "CPS-ML DataType language"
    mm = get_datatype_mm()
    return mm

@language('dummy-ent', '*.ent')
def entity_language():
    "CPS-ML Entity language"
    mm = get_entity_mm()
    return mm

@language('dummy-comm', '*.comm')
def communication_language():
    "CPS-ML Communication language"
    mm = get_communication_mm()
    return mm