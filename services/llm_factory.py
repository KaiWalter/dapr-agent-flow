"""LLM factory (TR005)

Creates a chat LLM client (OpenAIChatClient) configured for either
OpenAI or Azure OpenAI based on environment variables.

Provider selection precedence (TR005 enforced):
    1. Azure OpenAI when ALL of these are set (mandatory, no fallbacks):
             - AZURE_OPENAI_API_KEY
             - AZURE_OPENAI_ENDPOINT
             - AZURE_OPENAI_DEPLOYMENT
             - AZURE_OPENAI_API_VERSION
         Optional supporting env vars:
             - OPENAI_ORG_ID / OPENAI_PROJECT_ID (org/project passthrough)
             - AZURE_OPENAI_AD_TOKEN, AZURE_CLIENT_ID (advanced auth paths)
    2. OpenAI when OPENAI_API_KEY is set (model via OPENAI_MODEL or default 'gpt-4o-mini').

If neither provider can be resolved a RuntimeError is raised early so
agents/orchestrators fail fast with a clear message.

Rationale: The upstream dapr-agents library's OpenAIChatClient already
abstracts both OpenAI and Azure OpenAI via its base (OpenAIClientBase),
so returning an OpenAIChatClient instance in both cases keeps the rest
of the code uniform and future-proofs additional options (temperature, etc.).
"""

from __future__ import annotations

from dapr_agents import OpenAIChatClient
import logging
import os
from typing import Optional

logger = logging.getLogger("llm_factory")


def _all_present(*values: Optional[str]) -> bool:
    return all(v is not None and v.strip() != "" for v in values)


def create_chat_llm() -> OpenAIChatClient:  # noqa: D401
    """Return an OpenAIChatClient configured for Azure OpenAI or OpenAI.

    Azure takes precedence when its required env vars is fully present.
    Falls back to OpenAI. Raises RuntimeError if no viable configuration is found.
    """
    # --- Azure OpenAI path -------------------------------------------------
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    if _all_present(azure_api_key, azure_endpoint, azure_deployment, azure_api_version):
        try:
            client = OpenAIChatClient(
                # For Azure we supply azure_* fields; model left None so validator defaults to deployment
                api_key=azure_api_key,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=azure_api_version,
            )
            logger.info(
                "LLM provider selected: azure (deployment=%s, endpoint=%s, api_version=%s)",
                azure_deployment,
                azure_endpoint,
                azure_api_version,
            )
            return client
        except Exception as e:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to initialize Azure OpenAI client: {e}") from e

    # If partial Azure config is present, note it (debug) and continue to OpenAI fallback
    if any([azure_api_key, azure_endpoint, azure_deployment, azure_api_version]) and not _all_present(
        azure_api_key, azure_endpoint, azure_deployment, azure_api_version
    ):
        missing = [
            name
            for name, val in [
                ("AZURE_OPENAI_API_KEY", azure_api_key),
                ("AZURE_OPENAI_ENDPOINT", azure_endpoint),
                ("AZURE_OPENAI_DEPLOYMENT", azure_deployment),
                ("AZURE_OPENAI_API_VERSION", azure_api_version),
            ]
            if not (val and val.strip())
        ]
        logger.debug(
            "Azure OpenAI configuration incomplete; missing=%s. Falling back to OpenAI.",
            ",".join(missing),
        )

    # --- OpenAI path -------------------------------------------------------
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            client = OpenAIChatClient(model=model, api_key=openai_api_key)
            logger.info("LLM provider selected: openai (model=%s)", model)
            return client
        except Exception as e:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}") from e

    # --- Failure -----------------------------------------------------------
    raise RuntimeError(
        "No LLM provider configured. Set OPENAI_API_KEY (and optional OPENAI_MODEL) OR all of "
        "AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION."
    )


__all__ = ["create_chat_llm"]
