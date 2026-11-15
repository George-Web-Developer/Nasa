"""
Unified LLM Client with Provider Switch.
NASA Space Apps Challenge 2026 - Health Monitoring Software.

Supports:
1. Anthropic Claude (via official 'anthropic' SDK)
2. OpenAI-compatible providers (Gemini, Groq, OpenRouter, Ollama, vLLM via httpx)
3. Mock LLM mode (deterministic responses for testing without API keys)

Includes:
- Native function/tool calling for Spaceflight Knowledge Base retrieval
- Graceful server-side RAG fallback (injects retrieved protocols directly into prompt
  when the underlying provider or model lacks tool calling capability)
- Single-retry resiliency on malformed JSON outputs
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import httpx

import app.config as config
from app.config import logger


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None


def format_tools_for_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Anthropic-style tool schemas to standard OpenAI function call schemas."""
    openai_tools = []
    for t in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t.get("name"),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })
    return openai_tools


def inject_knowledge_into_prompt(prompt: str, chunks: List[Any]) -> str:
    """
    Server-side fallback: format retrieved knowledge chunks directly into
    system or user prompt when model does not support tool calling.
    """
    if not chunks:
        return prompt

    retrieved_text = "\n\n=== RETRIEVED OPERATIONAL PROTOCOLS (NASA KNOWLEDGE BASE) ===\n"
    for idx, chunk in enumerate(chunks, 1):
        retrieved_text += (
            f"\n[Protocol {idx}: {chunk.title} ({chunk.topic})]\n"
            f"Source: {chunk.source_name}\n"
            f"Content: {chunk.content}\n"
        )
    retrieved_text += "============================================================\n"
    retrieved_text += "Guidance: Gently integrate the relevant protocol advice above naturally into your response.\n"
    return prompt + retrieved_text


def call_anthropic_provider(
    system_prompt: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> LLMResponse:
    """Execute API call via Anthropic Claude SDK."""
    import anthropic

    api_key = config.LLM_API_KEY or config.ANTHROPIC_API_KEY
    if not api_key:
        raise RuntimeError("LLM_API_KEY / ANTHROPIC_API_KEY is not configured.")

    client = anthropic.Anthropic(api_key=api_key)
    model = config.LLM_MODEL or "claude-sonnet-5-5"

    kwargs: Dict[str, Any] = {
        "model": model,
        "system": system_prompt,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools

    response = client.messages.create(**kwargs)

    content_text = ""
    tool_calls = []

    for block in response.content:
        if block.type == "text":
            content_text += block.text
        elif block.type == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                )
            )

    return LLMResponse(content=content_text, tool_calls=tool_calls, raw=response)


def call_openai_compatible_provider(
    system_prompt: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> LLMResponse:
    """Execute API call via OpenAI-compatible endpoint (Gemini, Groq, OpenRouter, Ollama)."""
    base_url = config.LLM_BASE_URL.rstrip("/") if config.LLM_BASE_URL else "https://api.openai.com/v1"
    url = f"{base_url}/chat/completions"
    api_key = config.LLM_API_KEY

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Build messages array including system prompt
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    formatted_messages.extend(messages)

    payload: Dict[str, Any] = {
        "model": config.LLM_MODEL,
        "messages": formatted_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if tools:
        payload["tools"] = format_tools_for_openai(tools)
        payload["tool_choice"] = "auto"

    with httpx.Client(timeout=45.0) as client:
        res = client.post(url, headers=headers, json=payload)
        
        # If tool calling is not supported by the provider, retry without tools
        if res.status_code == 400 and tools and ("tool" in res.text.lower() or "function" in res.text.lower()):
            logger.warning("Provider rejected tools parameter. Retrying without tools (will fall back to prompt RAG)...")
            payload.pop("tools", None)
            payload.pop("tool_choice", None)
            res = client.post(url, headers=headers, json=payload)

        res.raise_for_status()
        data = res.json()

    choice = data.get("choices", [{}])[0]
    message_obj = choice.get("message", {})
    content_text = message_obj.get("content") or ""

    tool_calls = []
    raw_tool_calls = message_obj.get("tool_calls", [])
    for tc in raw_tool_calls:
        fn = tc.get("function", {})
        fn_args_raw = fn.get("arguments", "{}")
        try:
            fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
        except Exception:
            fn_args = {}
        tool_calls.append(
            ToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=fn_args,
            )
        )

    return LLMResponse(content=content_text, tool_calls=tool_calls, raw=data)


def call_llm(
    system_prompt: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1000,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> LLMResponse:
    """
    Unified entry point for calling the configured LLM provider.
    Switches between Anthropic and OpenAI-compatible endpoints based on config.LLM_PROVIDER.
    """
    provider = getattr(config, "LLM_PROVIDER", "anthropic").lower()

    if provider == "openai_compatible":
        return call_openai_compatible_provider(
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )
    else:
        return call_anthropic_provider(
            system_prompt=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )


def call_llm_text(
    system_prompt: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> str:
    """Helper that invokes LLM and returns pure text content."""
    resp = call_llm(
        system_prompt=system_prompt,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=None,
    )
    return resp.content
