import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AgentConfig:
    # Reads model from environment GROQ_MODEL. Default llama-3.3-70b-versatile
    # Model is routed through ADK's LiteLlm wrapper as "groq/<model>"
    model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    mcp_server_port: int = 8090
    max_iterations: int = 3
    pii_redaction_enabled: bool = True
    injection_detection_enabled: bool = True

config = AgentConfig()
