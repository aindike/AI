import os
from dotenv import load_dotenv
import autogen
import markdown
from flask import Flask, render_template, request, session, jsonify
from datetime import datetime
from collections import defaultdict

from agents import get_agents
from tools import plugin_image_guideline, plugin_image_suggestion
from utils import extract_requirements

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "any-random-secret")

# Load config for agents
config_list = autogen.config_list_from_json("OAI_CONFIG_LIST.json")
requirements_agent, code_agent = get_agents(config_list)

requirements = ["entity", "trigger", "fields", "logic"]
CONFIRM_KEYWORDS = {"yes", "y", "confirm", "ok", "correct", "proceed", "go ahead", "generate", "continue"}

# Store per-session code generation history
code_history_store = defaultdict(list)

def is_ready(reqs, confirmed):
    for r in requirements:
        value = reqs.get(r, "")
        if not value or "*pending*" in value.lower():
            return False
    return not confirmed

@app.route("/", methods=["GET", "POST"])
def chat():
    if "conversation" not in session:
        session["conversation"] = []
    if "reqs" not in session:
        session["reqs"] = {r: "" for r in requirements}
    if "confirmed" not in session:
        session["confirmed"] = False
    if "session_id" not in session:
        session["session_id"] = str(datetime.utcnow().timestamp())

    conversation = session["conversation"]
    reqs = session["reqs"]
    confirmed = session["confirmed"]
    session_id = session["session_id"]

    reply = ""
    user_input = ""

    if request.method == "GET":
        if not conversation:
            agent_reply = requirements_agent.generate_reply([{"content": "", "role": "user"}])
            conversation.append({"content": agent_reply, "role": "assistant"})
            session["conversation"] = conversation
            reply = agent_reply
        else:
            reply = conversation[-1]["content"] if conversation else ""
        return _render(reply, reqs, confirmed)

    user_input = request.form.get("user_input", "").strip()

    if "restart" in request.form:
        session.clear()
        session["conversation"] = []
        session["reqs"] = {r: "" for r in requirements}
        session["confirmed"] = False
        agent_reply = requirements_agent.generate_reply([{"content": "", "role": "user"}])
        session["conversation"] = [{"content": agent_reply, "role": "assistant"}]
        return _render(agent_reply, session["reqs"], False)

    if confirmed:
        if user_input:
            reqs["logic"] += "\n" + user_input
            code_block = _generate_code(reqs)
            reply = markdown.markdown(code_block, extensions=["fenced_code"])
            _save_code_history(session_id, reqs, code_block)
            return _render(reply, reqs, confirmed)
        else:
            reply = "Please type a change request or restart."
            return _render(reply, reqs, confirmed)

    if user_input:
        conversation.append({"content": user_input, "role": "user"})
        session["conversation"] = conversation

    reqs = extract_requirements(conversation, requirements_agent=requirements_agent)
    session["reqs"] = reqs

    missing = [r for r in requirements if not reqs.get(r)]
    all_ready = is_ready(reqs, confirmed)

    if (not missing) and (("confirm" in request.form) or (user_input.lower() in CONFIRM_KEYWORDS)):
        session["confirmed"] = True

        trigger = reqs["trigger"].lower()
        stage = "PostOperation"
        guideline = plugin_image_guideline(stage)
        suggestion = plugin_image_suggestion(trigger, stage)
        advice_message = f"\n\n---\n{guideline}\n\nImage Suggestion: {suggestion['Recommended']}\n"

        code_block = _generate_code(reqs, advice_message)
        reply = markdown.markdown(code_block, extensions=["fenced_code"])
        _save_code_history(session_id, reqs, code_block)
        return _render(reply, reqs, True)

    if all_ready:
        summary = (
            f"Just to summarize what you have provided so far:<br>"
            f"- <b>Entity</b>: {reqs['entity']}<br>"
            f"- <b>Trigger Event</b>: {reqs['trigger']}<br>"
            f"- <b>Field Involved</b>: {reqs['fields']}<br>"
            f"- <b>Business Logic</b>: {reqs['logic']}<br>"
            f"Please click <b>Confirm</b> in the UI to proceed with generating the code."
        )
        return _render(summary, reqs, False)

    if missing:
        agent_reply = requirements_agent.generate_reply(conversation)
        conversation.append({"content": agent_reply, "role": "assistant"})
        session["conversation"] = conversation
        reply = agent_reply
        return _render(reply, reqs, False)

    reply = "All requirements collected. Please review below and click **Confirm & Generate Code** when ready.<br>Or type 'confirm' to generate code."
    return _render(reply, reqs, False)

def _generate_code(reqs: dict, advice_message: str = "") -> str:
    prompt = (
        "Generate a Dynamics 365 plug-in in C# with the following specs:\n"
        f"Entity: {reqs['entity']}\n"
        f"Trigger: {reqs['trigger']}\n"
        f"Fields: {reqs['fields']}\n"
        f"Logic: {reqs['logic']}\n"
        f"{advice_message}"
    )
    return code_agent.generate_reply([{"content": prompt, "role": "user"}])

def _save_code_history(session_id, reqs, code):
    code_history_store[session_id].append({
        "timestamp": datetime.utcnow().isoformat(),
        "plugin_name": reqs.get("plugin_name", "UnknownPlugin"),
        "entity": reqs.get("entity"),
        "trigger": reqs.get("trigger"),
        "fields": reqs.get("fields"),
        "logic": reqs.get("logic"),
        "code": code
    })

@app.route("/regenerate", methods=["POST"])
def regenerate():
    new_logic = request.json.get("new_logic")
    session_id = session.get("session_id")
    if not code_history_store[session_id]:
        return jsonify({"error": "No previous plugin to regenerate."}), 400

    last = code_history_store[session_id][-1]
    prompt = f"""Regenerate this plugin with new logic:\n
Entity: {last['entity']}\nEvent: {last['trigger']}\nFields: {last['fields']}\nOld Logic: {last['logic']}\nNew Logic: {new_logic}"""

    modified_code = code_agent.generate_reply([{"content": prompt, "role": "user"}])
    return jsonify({"code": modified_code})

def _render(reply: str, reqs: dict, confirmed: bool):
    progress_lines = [f"**{r.capitalize()}**: {reqs.get(r, '*pending*') or '*pending*'}" for r in requirements]
    progress_md = "<br>".join(progress_lines)
    all_ready = is_ready(reqs, confirmed)
    return render_template(
        "chat.html",
        user_input="",
        reply=reply,
        progress_md=progress_md,
        all_ready=all_ready,
        confirmed=confirmed,
    )

if __name__ == "__main__":
    app.run(debug=True)
