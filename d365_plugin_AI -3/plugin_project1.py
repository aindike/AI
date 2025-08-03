import os
import subprocess

def create_plugin_solution(project_name, namespace, plugin_name):
    project_dir = os.path.join(os.getcwd(), project_name)
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

def build_plugin(project_dir):
    result = subprocess.run(["dotnet", "build"], cwd=project_dir, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def list_projects():
    return [
        d for d in os.listdir(os.getcwd())
        if os.path.isdir(d) and any(x.endswith(".csproj") for x in os.listdir(d))
    ]

def find_plugin_files(project_dir):
    return [f for f in os.listdir(project_dir) if f.endswith(".cs")]

