import os
import json
import openai
from plugin_project import create_plugin_solution, build_plugin, list_projects, find_plugin_files
from plugin_scaffold import list_solutions_webapi, list_plugin_assemblies
from plugin_deploy import deploy_with_webapi_profile, deploy_with_spn_profile
from d365_profiles import load_profiles
from plugin_project import get_project_dir

def agent_create_plugin(project_name, namespace, plugin_name):
    folder = create_plugin_solution(project_name, namespace, plugin_name)
    return f"✅ Created project at: {folder}"

def agent_build_plugin(project=None):
    projects = list_projects()
    if not project:
        if not projects:
            return "No projects found to build."
        elif len(projects) == 1:
            project = projects[0]
        else:
            return (
                "I found multiple projects: " +
                ", ".join(projects) +
                ".\nWhich project do you want to build?"
            )
    if project not in projects:
        return (
            f"Project '{project}' not found. " +
            "Available projects: " + ", ".join(projects)
        )
    out, err, code = build_plugin(project)
    return f"✅ Build OK for {project}." if code == 0 else f"❌ Build failed for {project}: {err}\n{out}"



def agent_list_projects():
    projects = list_projects()
    if not projects:
        return "No plugin projects found. Please create a project to get started."
    if len(projects) == 1:
        return (
            f"Available project: <b>{projects[0]}</b>.<br>"
            f"Do you want to use this project for your next action?"
        )
    return (
        "Available projects: " +
        ", ".join(f"<b>{p}</b>" for p in projects) +
        ".<br>Please specify which project you'd like to use for your next action."
    )


def agent_list_plugin_files(project):
    files = find_plugin_files(project)
    if not files:
        return f"No plugin files found in {project}."
    return f"Plugin files in {project}:\n" + "\n".join(files)

def agent_deploy_plugin(project, profile_name=None, assembly_name=None, solution_id=None, plugin_assembly_id=None):
    from plugin_scaffold import add_assembly_to_solution, list_solutions_webapi, list_plugin_assemblies

    # --- Profile validation ---
    profiles_dict = load_profiles()
    profiles = list(profiles_dict.keys())
    if not profile_name:
        if len(profiles) == 1:
            profile_name = profiles[0]
        else:
            return (
                "Available profiles: " +
                ", ".join(f"<b>{p}</b>" for p in profiles) +
                ".<br>Please specify which profile you would like to use for your deployment."
            )
    if profile_name not in profiles_dict:
        return f"Profile '{profile_name}' not found. Available profiles: {', '.join(profiles)}"
    prof = profiles_dict[profile_name]

    # --- Project validation ---
    projects = list_projects()
    if not project:
        if len(projects) == 1:
            project = projects[0]
        elif not projects:
            return "No plugin projects found. Please create a project first."
        else:
            return (
                "I found multiple projects: " +
                ", ".join(projects) +
                ".<br>Which project do you want to deploy?"
            )
    if project not in projects:
        return f"Project '{project}' not found. Available projects: {', '.join(projects)}"

    # --- Assembly search ---
    assemblies = list_plugin_assemblies(
        prof["env_url"], prof["app_id"], prof["tenant_id"], prof["client_secret"]
    )
    auto_msg = None
    if not plugin_assembly_id:
        possible_names = [n.lower() for n in [assembly_name, project] if n]
        matching = [a for a in assemblies if a["Name"].lower() in possible_names]
        if len(matching) == 1:
            plugin_assembly_id = matching[0]['PluginAssemblyId']
            auto_msg = f"✅ Found existing assembly '{matching[0]['Name']}' for project '{project}'. Will update assembly (ID: {plugin_assembly_id})."
        elif len(matching) > 1:
            # Ambiguous—ask, but do NOT list all assemblies unless necessary
            return (
                f"⚠️ Multiple assemblies found for name '{project}'.<br>"
                "If you want to update, please specify which one (provide the ID).<br>"
                "If this is a new project/assembly, say 'Deploy as new' to register a new assembly."
            )
        # else: no match, proceed as new—DO NOT show all assemblies

    # --- DLL location ---
    project_dir = get_project_dir(project)
    dll_path = None
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

    # --- Solution selection (ask for ALL deploys if not set) ---
    if not solution_id:
        solutions = list_solutions_webapi(
            prof["env_url"], prof["app_id"], prof["tenant_id"], prof["client_secret"]
        )
        if not solutions:
            return "No solutions found in your environment. Please create a solution first."
        if len(solutions) == 1:
            unique_name = solutions[0]["UniqueName"]
            return (
                f"Available solution: <b>{unique_name}</b>.<br>"
                f"Do you want to use this solution for your deployment? (Reply 'yes' to proceed, or specify another solution unique name.)"
            )
        return (
            "Available solutions: " +
            ", ".join(f"<b>{s['UniqueName']}</b>" for s in solutions) +
            ".<br>Please specify which solution you'd like to use for this deployment."
        )

    try:
        # --- New registration ---
        if not plugin_assembly_id:
            result = deploy_with_webapi_profile(
                dll_path=dll_path,
                profile_name=profile_name,
                assembly_name=assembly_name,
                solution_id=solution_id  # <-- always provided now
            )
            add_result = ""
            if solution_id:
                try:
                    # Re-fetch assemblies to get the ID of the new assembly
                    assemblies_after = list_plugin_assemblies(
                        prof["env_url"], prof["app_id"], prof["tenant_id"], prof["client_secret"]
                    )
                    match = [a for a in assemblies_after if a["Name"].lower() == (assembly_name or project).lower()]
                    if match:
                        add_result = add_assembly_to_solution(
                            env_url=prof["env_url"],
                            client_id=prof["app_id"],
                            tenant_id=prof["tenant_id"],
                            client_secret=prof["client_secret"],
                            assembly_id=match[0]["PluginAssemblyId"],
                            solution_unique_name=solution_id
                        )
                    else:
                        add_result = "⚠️ Could not find new assembly to add to solution after creation."
                except Exception as e:
                    add_result = f"⚠️ Deploy succeeded, but failed to add to solution: {e}"
            return (auto_msg + "<br>" if auto_msg else "") + f"{result}<br>{add_result}"
        else:
            # --- Update existing assembly ---
            deploy_result = deploy_with_spn_profile(
                dll_path=dll_path,
                profile_name=profile_name,
                plugin_assembly_id=plugin_assembly_id
            )
            add_result = ""
            if solution_id:
                try:
                    add_result = add_assembly_to_solution(
                        env_url=prof["env_url"],
                        client_id=prof["app_id"],
                        tenant_id=prof["tenant_id"],
                        client_secret=prof["client_secret"],
                        assembly_id=plugin_assembly_id,
                        solution_unique_name=solution_id
                    )
                except Exception as e:
                    add_result = f"⚠️ Deploy succeeded, but failed to add to solution: {e}"
            return (auto_msg + "<br>" if auto_msg else "") + f"{deploy_result}<br>{add_result}"
    except Exception as e:
        msg = str(e)
        # --- Specific error handling for D365 ---
        if "fullnames must be unique" in msg:
            matching = [a for a in assemblies if a["Name"].lower() == project.lower()]
            if matching:
                assembly_id = matching[0]['PluginAssemblyId']
                return (
                    f"❌ Deployment failed: A plugin assembly with the same name already exists (ID: {assembly_id}).<br>"
                    f"To update it, deploy using plugin_assembly_id: {assembly_id}.<br>"
                    f"Example: Deploy {project} using profile {profile_name} and plugin assembly id {assembly_id} "
                    f"and solution id {solution_id or '[your solution id]'}"
                )
            else:
                return (
                    "❌ Deployment failed: A plugin assembly with the same name already exists in your environment.<br>"
                    "To update the existing assembly, please specify the plugin_assembly_id.<br>"
                    "You can use the agent to 'list plugin assemblies' to find the right ID."
                )
        elif "Failed to add assembly to solution" in msg or "solution" in msg.lower():
            return (
                "❌ Deployment succeeded, but the specified solution was not found or is invalid.<br>"
                "Please check the solution unique name or GUID, or use the agent to 'list solutions' for your profile."
            )
        else:
            return f"❌ Deployment failed: {msg}"



def agent_add_plugin_class(project, class_name, namespace="DefaultNamespace"):
    project_dir = get_project_dir(project)
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

def agent_list_profiles():
    profiles = list(load_profiles().keys())
    if not profiles:
        return "No profiles are configured. Please add a profile before deploying or building plugins."
    if len(profiles) == 1:
        return (
            f"Available profile: <b>{profiles[0]}</b>. "
            f"Do you want to use this profile for your next action?"
        )
    return (
        "Available profiles: " +
        ", ".join(f"<b>{p}</b>" for p in profiles) +
        ". Please specify which profile you would like to use."
    )


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
            "required": ["project"]
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
    {
        "name": "agent_list_profiles",
        "description": "List all available D365 profiles for deployment and connection.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
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
    "agent_list_profiles": agent_list_profiles,
}

def chat_agent(user_msg, history=None, project=None):
    history = history or []
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    system_prompt = (
        "You are an AI assistant for managing Dynamics 365 plugin projects. "
        + (f"The user is currently working in the plugin project: '{project}'. " if project else "")
        + "Supported actions: create_plugin_solution, build_plugin_project, deploy_plugin_project, etc. "
        + "If the user says 'build', 'compile', 'deploy', or 'test', and does not specify a project, "
        + "assume they mean the current project. "
        + "If the project is missing but provided as context, use it. "
        + "Never ask the user for a project name if only one is available or if context is provided. "
        + "For commands like 'build my project', always use the context. "
        + "Be proactive and helpful, and avoid unnecessary clarification questions."
    )
    messages = [{"role": "system", "content": system_prompt}]
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
        print(f"Agent debug: fn_name={fn_name}, args={args}, injected_project={project}")
        # Inject project context if not present and available
        if 'project' in function_map[fn_name].__code__.co_varnames and 'project' not in args and project:
            print(f"Injecting project: {project}")
            args['project'] = project
        fn = function_map.get(fn_name)
        if not fn:
            return f"❌ Agent does not know how to perform: {fn_name}"
        try:
            print(f"Calling {fn_name} with args: {args}")
            result = fn(**args)
        except Exception as e:
            result = f"❌ Error running {fn_name}: {e}"
        return result
    else:
        return msg.get('content', 'No response.')



