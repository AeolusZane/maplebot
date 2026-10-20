"""Detect shared keys across different actions; potion tiers share one action."""
from collections import defaultdict


def normalize_key(key):
    value=str(key or '').strip().lower().replace(' ','')
    return {'pgup':'pageup','pgdown':'pagedown','pgdn':'pagedown','return':'enter','esc':'escape'}.get(value,value)


def conflicts(bindings):
    by_key=defaultdict(set)
    for action,key in bindings:
        key=normalize_key(key)
        if key:by_key[key].add(action)
    return {key:sorted(actions) for key,actions in by_key.items() if len(actions)>1}
