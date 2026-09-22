"""Minimal mock-enterprise world helpers.

State layout: state[system][table][record_id] = record (dict).
Used by the dataset builder to turn a seed state + actions into a final state,
and usable later if you want a live resolver that writes to the mock world.
"""
import copy


def find(state, system, table, match):
    """Return [(record_id, record)] in state[system][table] whose fields equal `match`."""
    tbl = state.get(system, {}).get(table, {})
    return [(rid, rec) for rid, rec in tbl.items()
            if all(rec.get(k) == v for k, v in match.items())]


def apply_action(state, action):
    """Apply one action dict in place. Ops: set, add_item, remove_item, clear, append."""
    recs = find(state, action["system"], action["table"], action["match"])
    if not recs:
        raise ValueError(f"no record matches {action['match']} in "
                         f"{action['system']}.{action['table']}")
    targets = recs if action.get("all") else recs[:1]
    op, field, val = action["op"], action["field"], action.get("value")
    for _, rec in targets:
        if op == "set":
            rec[field] = copy.deepcopy(val)
        elif op == "add_item":
            if val not in rec[field]:
                rec[field].append(val)
        elif op == "remove_item":
            rec[field] = [x for x in rec[field] if x != val]
        elif op == "clear":
            rec[field] = []
        elif op == "append":
            rec[field].append(val)
        else:
            raise ValueError(f"unknown op {op}")
    return state


def apply_actions(seed_state, actions):
    state = copy.deepcopy(seed_state)
    for a in actions:
        apply_action(state, a)
    return state
