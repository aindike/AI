import json
import re

def normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())

def load_field_map(entity_logical_name):
    path = f"fields/{entity_logical_name}_fields.json"
    with open(path, "r", encoding="utf-8") as f:
        fields_dict = json.load(f)
    out = {}
    for logical, info in fields_dict.items():
        display = info.get("displayName", "")
        if logical:
            out[logical.lower()] = logical
        if display:
            out[display.lower()] = logical
    return out

def extract_fields_from_text(field_map, text):
    norm_text = normalize(text)
    text_lower = text.lower()
    found = []

    # 1. Exact match (normalized)
    for display, logical in field_map.items():
        if normalize(display) == norm_text or normalize(logical) == norm_text:
            return [logical]

    # 2. Whole word or word-start matches
    tokens = set(re.findall(r'\b\w+\b', text_lower))
    for display, logical in field_map.items():
        candidates = [display.lower(), logical.lower()]
        for cand in candidates:
            if not cand:
                continue
            # Whole word match
            if cand in tokens:
                found.append(logical)
            # Word-start match (e.g., 'email' in 'emailaddress1')
            elif any(tok.startswith(cand) for tok in tokens):
                found.append(logical)

    if found:
        return list(dict.fromkeys(found))  # Remove duplicates, preserve order

    # 3. Substring in original text (weak fallback)
    for display, logical in field_map.items():
        if display in text_lower or logical in text_lower:
            found.append(logical)
    return list(dict.fromkeys(found))

# ---- Test code ----
if __name__ == "__main__":
    field_map = load_field_map("account")
    test_cases = [
        "I need to build a plugin to convert account table emailaddress1 to Camel case & and update Email with the new emailaddress1.",
        "Change the account email",
        "update Email",
        "update emailaddress1",
        "main phone",
        "number of employees",
        "statuscode",
        "statecode"
    ]
    for test in test_cases:
        fields_found = extract_fields_from_text(field_map, test)
        print(f"Test: {test}")
        print("Fields found:", fields_found)
        print("=" * 50)
