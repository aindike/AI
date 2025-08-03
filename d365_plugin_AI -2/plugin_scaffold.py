import os
import subprocess
import requests
from msal import ConfidentialClientApplication
import json
import re
import glob

def run_command(command, cwd=None, env=None):
    result = subprocess.run(command, shell=False, cwd=cwd, env=env)
    if result.returncode != 0:
        raise Exception(f"Command failed: {' '.join(command)}\nError: {result.stderr}")


def build_plugin(project_dir):
    result = subprocess.run(["dotnet", "build"], cwd=project_dir, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def get_pac_version():
    try:
        result = subprocess.run(["pac", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            match = re.search(r"Version:\s*([\d\.]+)", result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None

def get_deploy_command():
    version = get_pac_version()
    if version is None:
        return "push"
    try:
        major, minor, *_ = [int(x) for x in version.split(".")[:2]]
    except Exception:
        return "push"
    # 1.44 and above: use push, below: use deploy
    if (major, minor) >= (1, 44):
        return "push"
    else:
        return "deploy"

def get_assembly_file(project_dir):
    pattern = os.path.join(project_dir, "bin", "Debug", "**", "*.dll")
    files = glob.glob(pattern, recursive=True)
    files = [f for f in files if not os.path.basename(f).startswith(("Microsoft.", "System."))]
    if not files:
        raise Exception(f"No plugin DLL found at {pattern}. Did you build the project?")
    proj_name = os.path.basename(project_dir)
    for f in files:
        if proj_name.lower() in os.path.basename(f).lower():
            return f
    return files[0]

def deploy_plugin_connstr(project_dir, env_url, app_id, tenant_id, client_secret, plugin_assembly_id):
    command_type = get_deploy_command()
    connection_string = (
        f'AuthType=ClientSecret;'
        f'Url={env_url};'
        f'ClientId={app_id};'
        f'ClientSecret={client_secret};'
        f'TenantId={tenant_id}'
    )
    env = os.environ.copy()
    env["DATAVERSE_CONNECTION_STRING"] = connection_string

    if command_type == "push":
        assembly_path = get_assembly_file(project_dir)
        command = [
            "pac", "plugin", "push",
            "--pluginId", plugin_assembly_id,
            "--pluginFile", assembly_path,
            "--environment", env_url
        ]
    else:
        command = ["pac", "plugin", "deploy"]
    result = subprocess.run(
        command,
        cwd=project_dir,
        capture_output=True,
        text=True,
        env=env
    )
    return result.stdout, result.stderr, result.returncode

def deploy_plugin_pacprofile(project_dir, pac_profile_name, plugin_assembly_id, env_url=None):
    command_type = get_deploy_command()
    activate_pac_profile(pac_profile_name)
    if command_type == "push":
        assembly_path = get_assembly_file(project_dir)
        command = [
            "pac", "plugin", "push",
            "--pluginId", plugin_assembly_id,
            "--pluginFile", assembly_path
        ]
        if env_url:
            command.extend(["--environment", env_url])
    else:
        command = ["pac", "plugin", "deploy"]
    result = subprocess.run(
        command,
        cwd=project_dir,
        capture_output=True,
        text=True
    )
    return result.stdout, result.stderr, result.returncode

def get_access_token(tenant_id, client_id, client_secret, resource):
    app = ConfidentialClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=[f"{resource}/.default"])
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Token error: {result.get('error_description', str(result))}")

def list_solutions_webapi(env_url, client_id, tenant_id, client_secret):
    resource = env_url.rstrip("/")
    token = get_access_token(tenant_id, client_id, client_secret, resource)
    headers = {
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "odata.include-annotations=\"*\""
    }
    url = f"{resource}/api/data/v9.2/solutions?$select=solutionid,uniquename,friendlyname,version,ismanaged&$filter=ismanaged eq false"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Solution API error: {resp.status_code} {resp.text}")
    solutions = resp.json().get("value", [])
    return [
        {
            "UniqueName": s["uniquename"],
            "FriendlyName": s["friendlyname"],
            "IsManaged": s["ismanaged"],
            "Version": s["version"],
            "SolutionId": s["solutionid"]
        }
        for s in solutions
    ]

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
    return [
        {
            "PluginAssemblyId": a["pluginassemblyid"],
            "Name": a["name"]
        }
        for a in assemblies
    ]

def list_pac_profiles():
    result = subprocess.run(["pac", "auth", "list", "--json"], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    try:
        profiles = json.loads(result.stdout)
        return profiles
    except Exception:
        return []

def activate_pac_profile(profile_name):
    result = subprocess.run(["pac", "auth", "select", "--name", profile_name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to activate PAC profile {profile_name}: {result.stdout} {result.stderr}")
    
def add_assembly_to_solution(env_url, client_id, tenant_id, client_secret, assembly_id, solution_unique_name):
    token = get_access_token(tenant_id, client_id, client_secret, env_url.rstrip("/"))
    headers = {
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{env_url.rstrip('/')}/api/data/v9.2/AddSolutionComponent"
    payload = {
        "ComponentId": assembly_id,
        "ComponentType": 91,  # 91 = PluginAssembly
        "SolutionUniqueName": solution_unique_name,
        "AddRequiredComponents": False   # <--- must be included (True or False)
    }
    resp = requests.post(url, headers=headers, json=payload)
    if not resp.ok:
        raise Exception(f"Failed to add assembly to solution: {resp.text}")
    return "✅ Plugin assembly added to solution."


