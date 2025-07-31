from .thing2entity import build_entity_model, extract_entities, log_thing_info

def actor_to_entity_m2m(actor):
    # For now reuse existing functions if actors follow same structure
    components = [(actor, actor.name)]
    ent = extract_entities(components)
    return build_entity_model(ent)
