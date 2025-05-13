from .entity import get_entity_mm
from .datatype import get_datatype_mm
from .communication import get_communication_mm

from .utils import build_model

from textx import (get_location, metamodel_from_str,
                   metamodel_for_language,
                   register_language, clear_language_registrations)
import textx.scoping.providers as scoping_providers
import textx.scoping as scoping
import textx.exceptions


def register_languages():
    clear_language_registrations()
    global_repo = scoping.GlobalModelRepository()
    global_repo_provider = scoping_providers.PlainNameGlobalRepo()