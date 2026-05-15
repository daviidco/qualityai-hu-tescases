# Path + env are set up in main.py before this module is imported.
# agente_v2_json has sys.exit at module level — that guard only triggers
# if GROQ_API_KEY is missing, which main.py ensures is loaded first.

from agente_v2_json import RequirementsRefinerAgent as AgentJSON  # noqa: F401

__all__ = ["AgentJSON"]
