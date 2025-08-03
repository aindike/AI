"""
fetch_fields.py  –  Build one JSON file per table with full column metadata
--------------------------------------------------------------------------

• Reads `solution_entities.json`   (output of fetch_entities.py)
      format: { "<metadataid>": ["logical", "display"], ... }

• Uses CrmMetadataClient.get_attributes(logical_name)
  which returns every column, including lookup targets.

• Writes  fields/<logical>_fields.json   where each file is
      { logicalName_lower : {logicalName, displayName, type, targets} }

Run:
    python fetch_fields.py
"""

import os, json, traceback
from crm_metadata_client import CrmMetadataClient


# ----------------------------------------------------------------- helpers
def load_solution_entities(path: str = "solution_entities.json") -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"{path} not found.  Run fetch_entities.py first.")
    return json.load(open(path, "r", encoding="utf-8"))


def save_field_file(logical: str, attrs: list[dict]):
    os.makedirs("fields", exist_ok=True)
    # map by lower-case logical for easy lookup later
    field_map = {f["logicalName"].lower(): f for f in attrs}
    with open(f"fields/{logical}_fields.json", "w", encoding="utf-8") as f:
        json.dump(field_map, f, indent=2)


# ----------------------------------------------------------------- main
if __name__ == "__main__":
    client = CrmMetadataClient()            # loads crm_config.json + token
    entities = load_solution_entities()     # metadataid → [logical, display]

    for _, (logical, _) in entities.items():
        print(f"▶  {logical}")
        try:
            cols = client.get_attributes(logical)
            save_field_file(logical, cols)
            print(f"   ✓  saved fields/{logical}_fields.json "
                  f"({len(cols)} columns)")
        except Exception as exc:
            print(f"   ✗  failed: {exc}")
            traceback.print_exc()
