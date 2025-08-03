import os
import json
import openai
from plugin_project import create_plugin_solution, build_plugin, list_projects, find_plugin_files
from plugin_scaffold import list_solutions_webapi, list_plugin_assemblies
from plugin_deploy import deploy_with_webapi_profile, deploy_with_spn_profile
from d365_profiles import load_profiles

# ---- Utility functions to wrap business logic for the agent ----

def agent_create_plugin(project_name, namespace, plugin_name):
    folder = create_plugin_solution(project_name, namespace, plugin_name)
    return f"✅ Created project at: {folder}"

def agent_build_plugin(project):
    out, err, code = build_plugin(project)
    return "✅ Build OK." if code == 0 else f"❌ Build failed: {err}\n{out}"

def agent_list_projects():
    projects = list_projects()
    if not projects:
        return "No projects found."
    return "Projects:\n" + "\n".join(f"- {p}" for p in projects)

def agent_list_plugin_files(project):
    files = find_plugin_files(project)
    if not files:
        return f"No plugin files found in {project}."
    return f"Plugin files in {project}:\n" + "\n".join(files)

def agent_deploy_plugin(project, profile_name="default", assembly_name=None, solution_id=None, plugin_assembly_id=None):
    project_dir = os.path.abspath(project)
    dll_path = None
    # Try all target frameworks and build configs
    for config in ["Debug", "Release"]:
        for tf in ["net8.0", "net7.0", "net6.0", "net462", ""]:
            bin_dir = os.path.join(project_dir, "bin", config, tf)
            if not os.path.exists(bin_dir): continue
            for file in os.listdir(bin_dir):
                if file.lower().endswith(".dll") and not file.lower().startswith(("microsoft.", "system.")):
                    dll_path = os.path.join(bin_dir, file)
                    break
            if dll_path: break
        if dll_path: break
    if not dll_path:
        return f"❌ DLL not found in any bin folder for project {project}. Please build first."
    # Deploy
    if not plugin_assembly_id:
        # First deploy: new assembly
        return deploy_with_webapi_profile(
            dll_path=dll_path,
            profile_name=profile_name,
            assembly_name=assembly_name,
            solution_id=solution_id
        )
    else:
        # Update existing assembly
        return deploy_with_spn_profile(
            dll_path=dll_path,
            profile_name=profile_name,
            plugin_assembly_id=plugin_assembly_id
        )

def agent_add_plugin_class(project, class_name, namespace="DefaultNamespace"):
    project_dir = os.path.join(os.getcwd(), project)
    plugin_file_path = os.path.join(project_dir, f"{class_name}.cs")
    if os.path.exists(plugin_file_path):
        return "❌ Plugin class already exists!"
    code = f"""using Microsoft.Xrm.Sdk;
using System;

namespace {namespace}
{{
    public class {class_name} : IPlugin
    {{
        public void Execute(IServiceProvider serviceProvider)
        {{
            // TODO: Add plugin logic
        }}
    }}
}}"""
    with open(plugin_file_path, "w") as f:
        f.write(code)
    return f"✅ Plugin class '{class_name}' added to {project}"

def agent_list_solutions(profile_name="default"):
    profiles = load_profiles()
    if profile_name not in profiles:
        return "Profile not found."
    prof = profiles[profile_name]
    sols = list_solutions_webapi(
        prof["env_url"], prof["app_id"], prof["tenant_id"], prof["client_secret"]
    )
    return "Solutions:\n" + "\n".join(f"- {s['FriendlyName']} ({s['UniqueName']})" for s in sols)

def agent_list_assemblies(profile_name="default"):
    profiles = load_profiles()
    if profile_name not in profiles:
        return "Profile not found."
    prof = profiles[profile_name]
    assemblies = list_plugin_assemblies(
        prof["env_url"], prof["app_id"], prof["tenant_id"], prof["client_secret"]
    )
    return "Assemblies:\n" + "\n".join(f"- {a['Name']} ({a['PluginAssemblyId']})" for a in assemblies)

# ---- OpenAI function schemas ----
function_schemas = [
    {
        "name": "agent_create_plugin",
        "description": "Create a new plugin project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "namespace": {"type": "string"},
                "plugin_name": {"type": "string"}
            },
            "required": ["project_name", "namespace", "plugin_name"]
        }
    },
    {
        "name": "agent_build_plugin",
        "description": "Build an existing plugin project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string"}
            },
            "required": ["project"]
        }
    },
    {
        "name": "agent_list_projects",
        "description": "List all available plugin projects.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "agent_list_plugin_files",
        "description": "List plugin .cs files in a project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string"}
            },
            "required": ["project"]
        }
    },
    {
        "name": "agent_deploy_plugin",
        "description": "Deploy a plugin DLL. If plugin_assembly_id is given, will update an existing assembly, else will register a new one.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "profile_name": {"type": "string"},
                "assembly_name": {"type": "string"},
                "solution_id": {"type": "string"},
                "plugin_assembly_id": {"type": "string"}
            },
            "required": ["project", "profile_name"]
        }
    },
    {
        "name": "agent_add_plugin_class",
        "description": "Add a new plugin class (.cs) to a project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "class_name": {"type": "string"},
                "namespace": {"type": "string"}
            },
            "required": ["project", "class_name"]
        }
    },
    {
        "name": "agent_list_solutions",
        "description": "List D365 solutions for a profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "profile_name": {"type": "string"}
            },
            "required": ["profile_name"]
        }
    },
    {
        "name": "agent_list_assemblies",
        "description": "List plugin assemblies in a profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "profile_name": {"type": "string"}
            },
            "required": ["profile_name"]
        }
    },
]

function_map = {
    "agent_create_plugin": agent_create_plugin,
    "agent_build_plugin": agent_build_plugin,
    "agent_list_projects": agent_list_projects,
    "agent_list_plugin_files": agent_list_plugin_files,
    "agent_deploy_plugin": agent_deploy_plugin,
    "agent_add_plugin_class": agent_add_plugin_class,
    "agent_list_solutions": agent_list_solutions,
    "agent_list_assemblies": agent_list_assemblies,
}

# ---- Chat with agent function ----
def chat_agent(user_msg, history=None):
    history = history or []
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    # Prepare messages for OpenAI API
    messages = [{"role": "system", "content": "You are a helpful assistant for Dynamics 365 Plugin project management."}]
    messages += history
    messages.append({"role": "user", "content": user_msg})

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        functions=function_schemas,
        function_call="auto"
    )
    msg = response['choices'][0]['message']
    if msg.get('function_call'):
        fn_name = msg['function_call']['name']
        args = json.loads(msg['function_call']['arguments'])
        fn = function_map.get(fn_name)
        if not fn:
            return f"❌ Agent does not know how to perform: {fn_name}"
        try:
            result = fn(**args)
        except Exception as e:
            result = f"❌ Error running {fn_name}: {e}"
        return result
    else:
        return msg.get('content', 'No response.')

