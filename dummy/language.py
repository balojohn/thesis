from textx import language

from dummy.lang import (
    get_entity_mm
)

@language('dummy-ent', '*.ent')
def entity_language():
    """
    Register the language with the textX language manager.
    """
    mm = get_entity_mm()
    return mm