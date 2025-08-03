import json
import os
import re

def load_entity_map(path="entity_map.json"):
    """Loads entity display/logical name mapping."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_field_map(entity_logical_name):
    """Loads fields (display name/logical name) for given entity (dict format)."""
    path = f"fields/{entity_logical_name}_fields.json"
    if not os.path.exists(path):
        return {}, {}
    with open(path, "r", encoding="utf-8") as f:
        fields_dict = json.load(f)
    out = {}
    for logical, info in fields_dict.items():
        display = info.get("displayName", "")
        if logical:
            out[logical.lower()] = logical
        if display:
            out[display.lower()] = logical
    return out, fields_dict  # (field_map, full_fields_dict)

def normalize(text):
    """Normalize for matching (lowercase, strip, remove non-alphanum)."""
    return re.sub(r"[^a-z0-9]", "", text.lower())

def extract_fields_from_text(field_map, text):
    """
    Broad, inclusive field extractor.
    Returns all logical names whose display or logical name (lowercase) appears as substring in text.
    """
    norm_text = normalize(text)
    found = []
    for display, logical in field_map.items():
        norm_display = normalize(display)
        norm_logical = normalize(logical)
        if norm_display and norm_display in norm_text:
            found.append(logical)
        elif norm_logical and norm_logical in norm_text:
            found.append(logical)
    # Fallback: substring match in lowercased user text
    for display, logical in field_map.items():
        if display in text.lower() or logical in text.lower():
            if logical not in found:
                found.append(logical)
    # Remove duplicates, preserve order
    return list(dict.fromkeys(found))

def get_optionset_value(fields_json, field_logical, target_label):
    """Return the numeric value for an option label, or None."""
    info = fields_json.get(field_logical)
    if not info or "optionset" not in info:
        return None
    for opt in info["optionset"]:
        if opt["label"].lower() == target_label.lower():
            return opt["value"]
    return None

def get_lookup_targets(fields_json, field_logical):
    """Return a list of lookup target logical names, or [] if not a lookup."""
    info = fields_json.get(field_logical)
    if not info or "targets" not in info:
        return []
    return info["targets"]

def extract_requirements(conversation, requirements_agent=None):
    """
    Extracts entity, trigger, fields, and logic from conversation.
    Uses entity_map.json and fields/{entity}_fields.json for mapping and validation.
    If multiple fields are found, and requirements_agent is provided, uses the LLM agent to refine.
    """
    requirements = ["entity", "trigger", "fields", "logic"]
    reqs = {r: "" for r in requirements}
    text = " ".join(m["content"] for m in conversation if m["role"] == "user")

    # --- Entity extraction (map display name or logical name) ---
    entity_map = load_entity_map()
    found_entity = ""
    for display, logical in entity_map.items():
        if display.lower() in text.lower() or logical.lower() in text.lower():
            found_entity = logical
            break
    if found_entity:
        reqs["entity"] = found_entity

    # --- Trigger extraction ---
    for trig in ("create", "update", "delete", "assign"):
        if trig in text.lower():
            reqs["trigger"] = trig
            break

    # --- Field extraction ---
    found_fields = []
    if reqs["entity"]:
        field_map, _ = load_field_map(reqs["entity"])
        found_fields = extract_fields_from_text(field_map, text)
        # If multiple fields found and an agent is provided, refine with LLM
        if len(found_fields) > 1 and requirements_agent is not None:
            clarify_prompt = (
                f"The user provided this requirement:\n"
                f"\"{text.strip()}\"\n\n"
                f"The possible field matches (by logical name) are: {', '.join(found_fields)}.\n\n"
                "Given the above, which one is most likely correct? Reply with only the best logical name."
            )
            agent_reply = requirements_agent.generate_reply([{"content": clarify_prompt, "role": "user"}])
            found_fields = [agent_reply.strip()]
        reqs["fields"] = ", ".join(sorted(set(found_fields))) if found_fields else "*pending*"
    else:
        reqs["fields"] = "*pending*"

    # --- Logic extraction (use latest multi-word user message) ---
    for m in reversed(conversation):
        if m["role"] == "user" and len(m["content"].split()) > 4:
            reqs["logic"] = m["content"]
            break

    return reqs
