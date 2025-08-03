"""
crm_metadata_client.py
----------------------

Dataverse metadata client to fetch table attributes including:
- Lookup targets
- Local and global OptionSet values and labels

Uses crm_config.json for configuration.
"""

import json, os, time, requests
from typing import Dict, Any, List
from msal import ConfidentialClientApplication

class CrmMetadataClient:
    def __init__(self, cfg_path: str = "crm_config.json") -> None:
        self.config = self._load_cfg(cfg_path)
        self.token: str | None = None
        self.token_expiry: float = 0.0

    def get_attributes(self, table_logical_name: str) -> List[Dict[str, Any]]:
        self._ensure_token()
        api = self.config["resource"]
        hdr = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

        base = f"{api}/api/data/v9.2/EntityDefinitions(LogicalName='{table_logical_name}')"
        coll_url = f"{base}/Attributes?$select=LogicalName,DisplayName,AttributeType"
        resp = requests.get(coll_url, headers=hdr)
        resp.raise_for_status()

        attributes = []

        for attr in resp.json()["value"]:
            logical_name = attr["LogicalName"]
            display_name = ((attr.get("DisplayName") or {}).get("UserLocalizedLabel") or {}).get("Label", logical_name)
            attr_type = attr.get("AttributeType", "Unknown")

            col = {
                "logicalName": logical_name,
                "displayName": display_name,
                "type": attr_type,
                "targets": [],
                "optionset": []
            }

            # Fetch Lookup Targets
            if attr_type in ("Lookup", "Customer", "Owner"):
                lookup_url = (
                    f"{base}/Attributes(LogicalName='{logical_name}')"
                    "/Microsoft.Dynamics.CRM.LookupAttributeMetadata"
                )
                lookup_resp = requests.get(lookup_url, headers=hdr)
                if lookup_resp.status_code == 200:
                    col["targets"] = lookup_resp.json().get("Targets", [])

            # Fetch OptionSets (Picklist, State, Status, MultiSelectPicklist)
            if attr_type in ("Picklist", "State", "Status", "MultiSelectPicklist"):
                
                # Choose correct metadata type
                if logical_name == "statecode":
                    attr_metadata_type = "Microsoft.Dynamics.CRM.StateAttributeMetadata"
                elif logical_name == "statuscode":
                    attr_metadata_type = "Microsoft.Dynamics.CRM.StatusAttributeMetadata"
                else:
                    attr_metadata_type = "Microsoft.Dynamics.CRM.PicklistAttributeMetadata"

                picklist_url = (
                    f"{base}/Attributes(LogicalName='{logical_name}')/{attr_metadata_type}"
                    "?$expand=OptionSet($select=Options),GlobalOptionSet($select=Options)"
                )
                picklist_resp = requests.get(picklist_url, headers=hdr)

                if picklist_resp.status_code == 200:
                    data = picklist_resp.json()
                    opts = []
                    if data.get("OptionSet", {}).get("Options"):
                        opts = data["OptionSet"]["Options"]
                    elif data.get("GlobalOptionSet", {}).get("Options"):
                        opts = data["GlobalOptionSet"]["Options"]

                    col["optionset"] = [
                        {
                            "value": o["Value"],
                            "label": o["Label"]["UserLocalizedLabel"]["Label"]
                            if o["Label"].get("UserLocalizedLabel") else str(o["Value"])
                        }
                        for o in opts
                    ]
                else:
                    print(f"Picklist fetch failed [{logical_name}]: {picklist_resp.status_code}: {picklist_resp.text}")

            attributes.append(col)

        return attributes


    # ----- Private helper methods -----
    @staticmethod
    def _load_cfg(path: str) -> Dict[str, str]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{path} not found – create crm_config.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _ensure_token(self) -> None:
        if self.token and time.time() < self.token_expiry - 60:
            return
        cfg = self.config
        app = ConfidentialClientApplication(
            client_id=cfg["client_id"],
            authority=f"https://login.microsoftonline.com/{cfg['tenant_id']}",
            client_credential=cfg["client_secret"],
        )
        t = app.acquire_token_for_client(scopes=[f"{cfg['resource']}/.default"])
        if "access_token" not in t:
            raise RuntimeError(f"Token error: {t}")
        self.token = t["access_token"]
        self.token_expiry = int(time.time()) + int(t.get("expires_in", 3599))

# ----- CLI Test -----
if __name__ == "__main__":
    client = CrmMetadataClient()
    tbl = input("Enter table logical name: ").strip()
    meta = client.get_attributes(tbl)
    print(json.dumps(meta, indent=2))
