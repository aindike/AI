import requests
from msal import ConfidentialClientApplication

def get_access_token(tenant_id, client_id, client_secret, resource):
    app = ConfidentialClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    token = app.acquire_token_for_client(scopes=[f"{resource}/.default"])
    return token["access_token"]

def list_plugin_assemblies(env_url, client_id, tenant_id, client_secret):
    resource = env_url.rstrip("/")
    token = get_access_token(tenant_id, client_id, client_secret, resource)
    headers = {
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{resource}/api/data/v9.2/pluginassemblies?$select=pluginassemblyid,name"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"PluginAssembly API error: {resp.status_code} {resp.text}")
    assemblies = resp.json().get("value", [])
    # Filter out assemblies by name prefix
    ignore_prefixes = ("microsoft.", "system.", "activityfeeds", "adxstudio")
    filtered = [
        {
            "PluginAssemblyId": a["pluginassemblyid"],
            "Name": a["name"]
        }
        for a in assemblies
        if not a["name"].lower().startswith(ignore_prefixes)
    ]
    return sorted(filtered, key=lambda x: x["Name"].lower())

