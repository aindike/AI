# agents.py

from autogen import AssistantAgent

# You might want to import these or define them in this file:
# SYSTEM_PROMPT = ...
# CODE_AGENT_PROMPT = ...

def get_agents(config_list):
    SYSTEM_PROMPT = """
You are an expert assistant for generating Dynamics 365 plug-ins.

1. Start by asking: "What is the business logic you want to implement in Dynamics 365?" Let the user describe what they need in their own words.

2. After receiving their reply, analyze the description and identify:
   - The entity involved (e.g., contact, account, custom entity)
   - The trigger event (e.g., create, update, delete)
   - The fields involved (attributes the plugin will use)
   - The business logic (the rule or transformation itself)

3. If any of these details (entity, trigger, fields) are missing or unclear from the user's initial answer, ask follow-up questions for only those missing pieces—one at a time. Do NOT repeat questions for details already provided or confirmed.

4. Once you have confirmed all four requirements (entity, trigger, fields, logic), WAIT for the user to click Confirm in the UI to generate code. Do NOT ask for confirmation, do NOT summarize, and do NOT proceed further. Remain silent until the UI tells you to continue.

Always extract as much as possible from what the user has already provided before asking for more.
"""

    CODE_AGENT_PROMPT = """
You are an expert Dynamics 365 plug-in code generator.
The user will provide all required details. Output ONLY the C# plug-in code (no explanations) following best practices and .NET 6+ 'v2' SDK conventions.
"""

    requirements_agent = AssistantAgent(
        name="RequirementsAgent",
        system_message=SYSTEM_PROMPT,
        llm_config={"config_list": config_list},
    )
    code_agent = AssistantAgent(
        name="CodeAgent",
        system_message=CODE_AGENT_PROMPT,
        llm_config={"config_list": config_list},
    )
    return requirements_agent, code_agent
