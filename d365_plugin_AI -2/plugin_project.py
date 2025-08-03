import os
import subprocess

def get_project_dir(project_name):
    return os.path.abspath(os.path.join("Projects", project_name))

def create_plugin_solution(project_name, namespace, plugin_name):
    base_dir = os.path.join(os.getcwd(), "Projects")
    os.makedirs(base_dir, exist_ok=True)
    project_dir = os.path.join(base_dir, project_name)
    os.makedirs(project_dir, exist_ok=True)
    subprocess.run(["pac", "plugin", "init", "--outputDirectory", "."], cwd=project_dir, check=True)
    code = f"""using Microsoft.Xrm.Sdk;
using System;
namespace {namespace}
{{
    public class {plugin_name} : IPlugin
    {{
        public void Execute(IServiceProvider serviceProvider)
        {{
            // Plugin logic here
        }}
    }}
}}"""
    with open(os.path.join(project_dir, f"{plugin_name}.cs"), "w") as f:
        f.write(code)
    return project_dir

def build_plugin(project):
    project_dir = get_project_dir(project)
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory does not exist: {project_dir}")
    result = subprocess.run(["dotnet", "build"], cwd=project_dir, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def list_projects():
    projects_dir = os.path.join(os.getcwd(), "Projects")
    if not os.path.isdir(projects_dir):
        return []
    return [
        d for d in os.listdir(projects_dir)
        if os.path.isdir(os.path.join(projects_dir, d)) and
           any(x.endswith(".csproj") for x in os.listdir(os.path.join(projects_dir, d)))
    ]

def find_plugin_files(project):
    project_dir = get_project_dir(project)
    return [f for f in os.listdir(project_dir) if f.endswith(".cs")]
