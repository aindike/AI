from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from agent import chat_agent
from d365_profiles import load_profiles
from authlib.integrations.flask_client import OAuth
import os
import requests
import subprocess
import json
from flask_session import Session
app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
app.secret_key = os.environ.get('APP_SECRET', 'dev-secret')
app.config['SESSION_PERMANENT'] = False  # Make session non-permanent for easier dev debug

oauth = OAuth(app)

# ===== Azure DevOps OAuth2 Setup =====

with open('azdo_oauth.json', 'r') as f:
    azdo_config = json.load(f)
# Load org/project mapping
with open('azdo_projects.json', 'r') as f:
    azdo_projects = json.load(f)

app.config['AZDO_CLIENT_ID'] = azdo_config['AZDO_CLIENT_ID']
app.config['AZDO_CLIENT_SECRET'] = azdo_config['AZDO_CLIENT_SECRET']
app.config['AZDO_TENANT_ID'] = azdo_config['AZDO_TENANT_ID']
AZDO_AUTHORIZE_URL = f'https://login.microsoftonline.com/{app.config["AZDO_TENANT_ID"]}/oauth2/v2.0/authorize'
AZDO_TOKEN_URL = f'https://login.microsoftonline.com/{app.config["AZDO_TENANT_ID"]}/oauth2/v2.0/token'
AZDO_API_BASE = 'https://dev.azure.com/'

oauth.register(
    name='azdo',
    client_id=app.config['AZDO_CLIENT_ID'],
    client_secret=app.config['AZDO_CLIENT_SECRET'],
    server_metadata_url=f'https://login.microsoftonline.com/{app.config["AZDO_TENANT_ID"]}/v2.0/.well-known/openid-configuration',
    api_base_url='https://dev.azure.com/',
    client_kwargs={
        'scope': '499b84ac-1321-427f-aa17-267ca6975798/.default openid profile offline_access',
    }
)

@app.route("/", methods=["GET"])
def chat_ui():
    print("[/] SESSION KEYS:", list(session.keys()))
    return render_template("chat.html")

@app.route("/login/azdo")
def login_azdo():
    print("[/login/azdo] SESSION KEYS:", list(session.keys()))
    return oauth.azdo.authorize_redirect(redirect_uri=url_for('azdo_callback', _external=True))

@app.route("/callback/azdo")
def azdo_callback():
    print("[/callback/azdo] SESSION KEYS BEFORE:", list(session.keys()))
    token = oauth.azdo.authorize_access_token()
    session["azdo_token"] = token
    print("[/callback/azdo] SESSION KEYS AFTER:", list(session.keys()))
    return redirect(url_for("chat_ui"))

@app.route("/api/connected")
def api_connected():
    print("[/api/connected] SESSION KEYS:", list(session.keys()))
    return jsonify({
        "azdo": "azdo_token" in session,
    })

@app.route("/azdo_projects")
def azdo_projects_api():
    return jsonify({"azdo_projects": azdo_projects})

@app.route("/chat", methods=["POST"])
def chat():
    try:
        print("[/chat] SESSION KEYS:", list(session.keys()))
        data = request.get_json()
        user_msg = data.get("message", "").strip()
        history = data.get("history", [])
        azdo_project = data.get("azdo_project")   # Azure DevOps repo selected
        plugin_project = data.get("project")      # Local plugin project selected

        print("---- /chat called ----")
        print("user_msg:", user_msg)
        print("azdo_project (DevOps repo):", azdo_project)
        print("plugin_project (local):", plugin_project)
        print("azdo_token in session:", "azdo_token" in session)
        print("Known DevOps projects:", list(azdo_projects.keys()))

       

        if (
            "push" in user_msg.lower()
            and "azure" in user_msg.lower()
            and "azdo_token" in session
            and azdo_project
            and azdo_project in azdo_projects
            and plugin_project
        ):
            repo_root = os.path.abspath(f"projects")  # Adjust to your actual repo root folder name
            plugin_path = os.path.join(repo_root, plugin_project)
            org = azdo_projects[azdo_project]["org"]
            devops_proj = azdo_projects[azdo_project]["project"]
            repo = azdo_projects[azdo_project].get("repo", azdo_project)
            repo_url = f"https://dev.azure.com/{org}/{devops_proj}/_git/{repo}"
            token = session["azdo_token"]["access_token"]

            print(f"Matched DevOps: org={org}, project={devops_proj}, repo={repo}, repo_url={repo_url}, plugin_path={plugin_path}")

            if not os.path.exists(plugin_path):
                reply = f"❌ Plugin project path does not exist: {plugin_path}"
                print(reply)
                return jsonify({"reply": reply})

            try:
                git_push_project(repo_root, repo_url, token, plugin_project)
                reply = f"✅ Pushed {plugin_project} to Azure DevOps repo: {repo_url}"
            except Exception as e:
                print("Exception during git push:", e)
                reply = f"❌ Failed to push {plugin_project} to Azure DevOps: {e}"
            return jsonify({"reply": reply})

        if "push" in user_msg.lower() and "azure" in user_msg.lower():
            if not azdo_project:
                return jsonify({"reply": "❌ No Azure DevOps project selected!"})
            if azdo_project not in azdo_projects:
                return jsonify({"reply": f"❌ DevOps project '{azdo_project}' not found in mapping!"})
            if not plugin_project:
                return jsonify({"reply": "❌ No local plugin project selected!"})
            if "azdo_token" not in session:
                return jsonify({"reply": "❌ You must connect to Azure DevOps SSO first!"})
        
        if not user_msg:
            return jsonify({"reply": "I didn't receive any input."}), 400
        # Pass plugin_project to the agent as context!
        reply = chat_agent(user_msg, history, project=plugin_project)
        return jsonify({"reply": reply})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"reply": f"❌ Server error: {e}"}), 500



def git_push_project(repo_root, repo_url, token, subfolder, branch="main"):
    import subprocess, os

    remote_url = repo_url.replace('https://', f'https://{token}@')
    cmds = [
        ["git", "init"],
        ["git", "branch", "-M", branch],
    ]
    try:
        subprocess.run(["git", "remote", "remove", "origin"], cwd=repo_root, check=True)
    except subprocess.CalledProcessError:
        pass

    cmds += [
        ["git", "remote", "add", "origin", remote_url],
        ["git", "config", "user.name", "Ajith"],
        ["git", "config", "user.email", "Ajith@publicissapientengineering.onmicrosoft.com"],
        ["git", "add", subfolder],  # <--- Add only the specific subfolder
        ["git", "commit", "-m", f"Push {subfolder} plugin project", "--allow-empty"],
        ["git", "push", "-u", "origin", branch, "--force"]
    ]

    for cmd in cmds:
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=repo_root, check=True)



@app.route("/profiles", methods=["GET"])
def get_profiles():
    profiles = list(load_profiles().keys())
    return jsonify({"profiles": profiles})

@app.route("/projects", methods=["GET"])
def get_projects():
    from plugin_project import list_projects
    return jsonify({"projects": list_projects()})

if __name__ == "__main__":
    app.run(debug=True)
