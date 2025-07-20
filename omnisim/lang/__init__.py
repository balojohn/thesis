from .communication import get_communication_mm
from .datatype import get_datatype_mm
from .entity import get_entity_mm
from .environment import get_env_mm
from .thing import get_thing_mm
from .utils import build_model

# from textx import (get_location, metamodel_from_str,
#                    metamodel_for_language,
#                    register_language, clear_language_registrations)
# import textx.scoping.providers as scoping_providers
# import textx.scoping as scoping
# def register_language():
#     clear_language_registrations()
#     global_repo = scoping.GlobalModelRepository()
#     global_repo_provider = scoping_providers.PlainNameGlobalRepo()
#     thing = get_thing_mm()