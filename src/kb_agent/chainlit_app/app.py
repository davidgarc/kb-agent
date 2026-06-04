import json
import os
import uuid

import chainlit as cl
import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_APP_ID = os.getenv("CHAINLIT_DEFAULT_APP_ID", "APP001")


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label="Architecture", message="What is the current architecture for APP001?"),
        cl.Starter(label="Latency causes", message="What recent incidents might explain payment API latency?"),
        cl.Starter(label="Dependency impact", message="Which dependencies could impact APP001 if the database is degraded?"),
        cl.Starter(label="Manifest drift", message="Compare the manifest resources with the architecture docs. What looks inconsistent?"),
    ]


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("session_id", str(uuid.uuid4()))
    cl.user_session.set("app_id", DEFAULT_APP_ID)
    app_name = await _app_name(DEFAULT_APP_ID)
    await cl.Message(
        content=(
            f"Selected app: **{DEFAULT_APP_ID}**"
            + (f" - {app_name}" if app_name else "")
            + "\n\nAsk a troubleshooting question, or mention a different app ID such as APP002."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    app_id = _extract_app_id(message.content) or cl.user_session.get("app_id") or DEFAULT_APP_ID
    cl.user_session.set("app_id", app_id)
    session_id = cl.user_session.get("session_id") or str(uuid.uuid4())
    response = cl.Message(content="")

    final_payload = None
    async with httpx.AsyncClient(timeout=90) as client:
        async with client.stream(
            "POST",
            f"{API_BASE_URL}/chat/stream",
            json={"session_id": session_id, "app_id": app_id, "message": message.content},
        ) as stream:
            async for line in stream.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line.removeprefix("data: "))
                if event["type"] == "token":
                    await response.stream_token(event["text"])
                elif event["type"] == "final":
                    final_payload = event["payload"]

    await response.send()
    if final_payload:
        await _render_structured_sections(final_payload)


async def _render_structured_sections(payload: dict) -> None:
    likely = payload.get("likely_causes", [])
    checks = payload.get("recommended_next_checks", [])
    evidence = payload.get("evidence", [])
    missing = payload.get("missing_data", [])

    if likely:
        content = "\n".join(f"- **{item['title']}** ({item['confidence']}): {item['why']}" for item in likely)
        await cl.Message(content=f"### Likely causes\n{content}").send()
    if checks:
        content = "\n".join(f"- {item['action']} ({item.get('owner_hint') or 'owner TBD'})" for item in checks)
        await cl.Message(content=f"### Next checks\n{content}").send()
    if evidence:
        content = "\n\n".join(f"**{item['id']}** - `{item['source_type']}`\n{item['snippet']}\n_Source: {item['source_ref']}_" for item in evidence)
        await cl.Message(content=f"### Evidence\n{content}").send()
    if missing:
        await cl.Message(content="### Missing data\n" + "\n".join(f"- {item}" for item in missing)).send()


async def _app_name(app_id: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{API_BASE_URL}/apps/{app_id}")
            if response.status_code == 404:
                await client.post(f"{API_BASE_URL}/ingest/all")
                response = await client.get(f"{API_BASE_URL}/apps/{app_id}")
            response.raise_for_status()
            return response.json().get("name")
    except Exception:
        return None


def _extract_app_id(text: str) -> str | None:
    import re

    match = re.search(r"\bAPP\d{3}\b", text.upper())
    return match.group(0) if match else None

