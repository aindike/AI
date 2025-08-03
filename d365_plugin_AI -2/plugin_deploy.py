import os
import json
import base64
import requests
import msal
import shutil
import subprocess

# -------- Profile loader --------
def load_profile(profile_name="default", json_path="d365_profiles.json"):
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Cannot find profile file: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        profiles = json.load(f)
    if profile_name not in profiles:
        raise ValueError(f"Profile '{profile_name}' not found in {json_path}")
    return profiles[profile_name]

# -------- Errors --------
class WebApiError(Exception):
    pass

class PacError(Exception):
    pass

def deploy_with_webapi_profile(
    dll_path,
    profile_name="default",
    json_path="d365_profiles.json",
    assembly_name=None,
    solution_id=None         # <-- added
):
    prof = load_profile(profile_name, json_path)
    env_url = prof["env_url"]
    client_id = prof["app_id"]
    tenant_id = prof["tenant_id"]
    client_secret = prof["client_secret"]

    scope = [f"{env_url}/.default"]
    authority = f"https://login.microsoftonline.com/{tenant_id}"

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority
    )
    token_result = app.acquire_token_for_client(scopes=scope)
    if "access_token" not in token_result:
        raise WebApiError(token_result.get("error_description") or str(token_result))
    token = token_result["access_token"]

    if not assembly_name:
        assembly_name = os.path.splitext(os.path.basename(dll_path))[0]

    with open(dll_path, "rb") as f:
        dll_b64 = base64.b64encode(f.read()).decode()

    url = f"{env_url}/api/data/v9.2/pluginassemblies"
    if solution_id:
        url += f"?solutionid={solution_id}"   # <-- associate with solution

    payload = {
        "name": assembly_name,
        "content": dll_b64,
        "isolationmode": 2,
        "sourcetype": 0
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, json=payload, headers=headers)
    if not resp.ok:
        raise WebApiError(f"Failed to deploy assembly: {resp.text}")

    # Optional: PublishAllXml to make it live right away
    requests.post(f"{env_url}/api/data/v9.2/PublishAllXml", headers=headers, json={})

    return f"✅ Deployed plugin assembly '{assembly_name}' using Web API profile '{profile_name}'" + (f" into solution {solution_id}" if solution_id else "") + "."


# -------- CLI deploy for updates --------
MIN_PAC_VERSION = (1, 17, 6)

def ensure_pac():
    if not shutil.which("pac"):
        raise PacError("The Power Platform CLI (`pac`) is not on PATH.")
    out = subprocess.run(["pac", "--version"], capture_output=True, text=True).stdout
    parts = [int(p) for p in out.strip().split(".")[:3] if p.isdigit()]
    if tuple(parts) < MIN_PAC_VERSION:
        raise PacError(f"`pac` version {out.strip()} is too old. Need >= {'.'.join(map(str, MIN_PAC_VERSION))}.")
    return out.strip()

def ensure_auth_with_spn(env_url, client_id, tenant_id, client_secret):
    args = [
        "pac", "auth", "create",
        "--environment", env_url,
        "--tenant", tenant_id,
        "--applicationId", client_id,
        "--clientSecret", client_secret
    ]
    subprocess.run(args, check=True)

def push_plugin(dll_path, env_url):
    if not os.path.exists(dll_path):
        raise FileNotFoundError(dll_path)
    ext = os.path.splitext(dll_path)[1].lower()
    typ = "Assembly" if ext == ".dll" else "Package"
    cmd = [
        "pac", "plugin", "push",
        "--pluginFile", dll_path,
        "--type", typ,
        "--environment", env_url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise PacError(result.stderr or result.stdout)
    return result.stdout

def deploy_with_spn_profile(
    dll_path,
    profile_name="default",
    plugin_assembly_id=None,       # <- Accept as argument
    json_path="d365_profiles.json"
):
    prof = load_profile(profile_name, json_path)
    env_url = prof["env_url"]
    client_id = prof["app_id"]
    tenant_id = prof["tenant_id"]
    client_secret = prof["client_secret"]

    ensure_pac()
    ensure_auth_with_spn(env_url, client_id, tenant_id, client_secret)
    if not plugin_assembly_id:
        raise ValueError("plugin_assembly_id is required for update")
    return push_plugin_with_id(dll_path, env_url, plugin_assembly_id)

def push_plugin_with_id(dll_path, env_url, plugin_assembly_id):
    cmd = [
        "pac", "plugin", "push",
        "--pluginId", plugin_assembly_id,
        "--pluginFile", dll_path,
        "--environment", env_url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr or result.stdout)
    return result.stdout



