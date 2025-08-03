# fetch_entities.py
import json
import requests
from msal import ConfidentialClientApplication

def load_crm_config(path="crm_config.json"):
    with open(path, "r") as f:
        return json.load(f)

def load_solution_config(path="solution_config.json"):
    with open(path, "r") as f:
        return json.load(f)

def get_token(cfg):
    app = ConfidentialClientApplication(
        cfg["client_id"],
        authority=f"https://login.microsoftonline.com/{cfg['tenant_id']}",
        client_credential=cfg["client_secret"],
    )
    result = app.acquire_token_for_client(scopes=[f"{cfg['resource']}/.default"])
    if "access_token" not in result:
        raise Exception(f"Failed to acquire token: {result}")
    return result["access_token"]

def fetch_entities_for_solution(solution_unique_name):
    cfg = load_crm_config()
    token = get_token(cfg)
    sol_url = f"{cfg['resource']}/api/data/v9.2/solutions?$filter=uniquename eq '{solution_unique_name}'&$select=solutionid"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    res = requests.get(sol_url, headers=headers)
    res.raise_for_status()
    solutions = res.json()["value"]
    if not solutions:
        raise Exception(f"No solution found for unique name: {solution_unique_name}")
    solution_id = solutions[0]["solutionid"]

    # Use _solutionid_value for the lookup
    url = f"{cfg['resource']}/api/data/v9.2/solutioncomponents?$filter=_solutionid_value eq '{solution_id}' and componenttype eq 1&$select=objectid"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    entity_objectids = [sc["objectid"] for sc in res.json()["value"]]
    print(f"Found {len(entity_objectids)} entity components in solution.")

    # Now fetch display/logical names for those entities
    entities = {}
    for oid in entity_objectids:
        ent_url = f"{cfg['resource']}/api/data/v9.2/EntityDefinitions({oid})?$select=LogicalName,DisplayName"
        res2 = requests.get(ent_url, headers=headers)
        res2.raise_for_status()
        ent = res2.json()
        logical = ent["LogicalName"]
        display = ent["DisplayName"]["UserLocalizedLabel"]["Label"] if ent["DisplayName"] and ent["DisplayName"].get("UserLocalizedLabel") else logical
        entities[oid] = (logical, display)
    return entities

if __name__ == "__main__":
    solution_cfg = load_solution_config()
    entities = fetch_entities_for_solution(solution_cfg["solution_unique_name"])
    # Save both dict and a simpler entity_map.json if you want
    with open("solution_entities.json", "w") as f:
        json.dump(entities, f, indent=2)
    # Build a display/logical map if you still need it elsewhere
    entity_map = {}
    for metadataid, (ln, dn) in entities.items():
        entity_map[ln.lower()] = ln
        entity_map[dn.lower()] = ln
    with open("entity_map.json", "w") as f:
        json.dump(entity_map, f, indent=2)
    print("Entity map and solution_entities.json saved!")
