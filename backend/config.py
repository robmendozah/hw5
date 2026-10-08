"""Configuration and hard limits for the Campus Customs agent team.

Every limit that controls token spend or loop behaviour is a named constant
here so it can be audited in one place and quoted accurately in
output/harness.md. The documentation must match these values.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------- paths
HW5_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HW5_ROOT.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
OUTPUT_DIR = HW5_ROOT / "output"
AUDIT_TRAIL_PATH = OUTPUT_DIR / "audit_trail.json"
MCP_SERVER_SCRIPT = HW5_ROOT / "mcp_server" / "server.py"

# .env lives at the AI Foundations root, one level above hw5/.
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(HW5_ROOT / ".env", override=False)

# ---------------------------------------------------------------- model
# The only model any agent may use.
MODEL_NAME = "gpt-6-luna"

# Portkey exposes an OpenAI-compatible gateway.
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
PORTKEY_API_KEY_ENV = "PORTKEY_API_KEY"

# gpt-6-luna refuses function tools on the chat-completions endpoint unless
# reasoning effort is 'none'. Every agent here uses tools, so this is required
# rather than a tuning choice.
REASONING_EFFORT = "none"

# ---------------------------------------------------------------- limits
# Model requests one agent may make in a single run. Caps the inner
# think -> call tool -> think loop.
MAX_AGENT_LOOP_STEPS = 8

# Total delegations across a whole ticket run, summed over all agents.
MAX_TOTAL_DELEGATIONS = 6

# How deep a delegation chain may nest. Boss -> Inventory -> Accounting is
# depth 2; a fourth hop is refused.
MAX_DELEGATION_DEPTH = 3

# MCP tool calls across a whole ticket run, summed over all agents.
MAX_TOOL_CALLS_PER_RUN = 20

# Characters of a single MCP tool result passed back to a model. Results
# above this are truncated with an explicit marker, never silently.
MAX_TOOL_RESULT_CHARS = 6000

# Characters of free text accepted in one delegation request, so agents
# cannot forward whole transcripts to each other.
MAX_DELEGATION_CONTEXT_CHARS = 1500

# Wall-clock ceiling for one ticket run.
RUN_TIMEOUT_SECONDS = 300

# Same agent pair, same ticket: refuse after this many repeats. Blocks
# A -> B -> A -> B ping-pong even when the global caps still allow it.
MAX_REPEAT_DELEGATIONS_PER_PAIR = 2


class ConfigError(RuntimeError):
    """Raised when required configuration is absent."""


def get_portkey_api_key() -> str:
    """Read the Portkey key from the environment.

    Never defaulted, never logged, never written to the audit trail.
    """
    key = os.getenv(PORTKEY_API_KEY_ENV)
    if not key:
        raise ConfigError(
            f"{PORTKEY_API_KEY_ENV} is not set. Add it to the .env file at "
            f"{PROJECT_ROOT / '.env'}. It must never be hard-coded in source."
        )
    return key


def limits_summary() -> dict[str, object]:
    """The implemented limits, for documentation and audit records."""
    return {
        "model": MODEL_NAME,
        "max_agent_loop_steps": MAX_AGENT_LOOP_STEPS,
        "max_total_delegations": MAX_TOTAL_DELEGATIONS,
        "max_delegation_depth": MAX_DELEGATION_DEPTH,
        "max_tool_calls_per_run": MAX_TOOL_CALLS_PER_RUN,
        "max_tool_result_chars": MAX_TOOL_RESULT_CHARS,
        "max_delegation_context_chars": MAX_DELEGATION_CONTEXT_CHARS,
        "max_repeat_delegations_per_pair": MAX_REPEAT_DELEGATIONS_PER_PAIR,
        "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
    }
