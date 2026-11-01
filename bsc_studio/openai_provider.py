from __future__ import annotations

import base64
import json
import time
import wave
from pathlib import Path
from urllib.parse import quote

import httpx
import websocket

from bsc_radio.codex_provider import (_FACT_SCHEMA, _REWRITE_SCHEMA, _SCRIPT_SCHEMA, _TOPIC_SCHEMA, _VERDICT_SCHEMA)

REALTIME_VOICES = ("alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar")


class OpenAIEditorialProvider:
    def __init__(self, key: str, model: str, prompts: Path):
        if not key.strip():
            raise ValueError("Renseignez votre clé API OpenAI dans les paramètres.")
        self.key, self.model, self.prompts = key, model, prompts

    def _json(self, prompt_name: str, payload: dict, schema: dict):
        common = (self.prompts / "common.md").read_text(encoding="utf-8")
        prompt = self.prompts / f"{prompt_name}.md"
        instructions = common + "\n" + (prompt.read_text(encoding="utf-8") if prompt.exists() else prompt_name)
        response = httpx.post("https://api.openai.com/v1/responses", timeout=180,
                              headers={"Authorization": f"Bearer {self.key}"}, json={
                                  "model": self.model, "store": False, "instructions": instructions,
                                  "input": json.dumps(payload, ensure_ascii=False),
                                  "text": {"format": {"type": "json_schema", "name": schema["title"], "strict": True,
                                                       "schema": {k: v for k, v in schema.items() if k != "title"}}}})
        if response.is_error:
            raise RuntimeError(f"OpenAI a refusé la génération (HTTP {response.status_code}). Vérifiez la clé, le modèle et le crédit API.")
        data = response.json()
        if data.get("status") != "completed":
            raise RuntimeError("OpenAI n’a pas terminé le texte. Le brouillon existant est conservé.")
        text = "".join(part.get("text", "") for item in data.get("output", []) for part in item.get("content", []) if part.get("type") == "output_text")
        return json.loads(text)

    def extract_facts(self, title, text, source):
        return self._json("extract_facts", {"title": title, "text": text, "source": source}, _FACT_SCHEMA)["facts"]

    def cluster(self, facts):
        return self._json("cluster", {"facts": facts}, _TOPIC_SCHEMA)

    def write(self, fmt, facts, context):
        return self._json(f"write_{fmt}", {"facts": facts, "context": context}, _SCRIPT_SCHEMA)["lines"]

    def verify(self, sentence, facts):
        return self._json("verify", {"sentence": sentence, "facts": facts}, _VERDICT_SCHEMA)

    def rewrite(self, sentence, facts):
        return self._json("verify", {"sentence": sentence, "facts": facts,
                                      "task": "Réécris uniquement les éléments soutenus par les faits."}, _REWRITE_SCHEMA)["text"]


def synthesize(key: str, model: str, text: str, voice: str, output: Path, direction: str = "") -> None:
    if not key.strip():
        raise ValueError("Renseignez votre clé API OpenAI dans les paramètres.")
    if voice not in REALTIME_VOICES:
        raise ValueError("Choisissez une voix API disponible. L’accès à Rivage n’est pas confirmé.")
    socket = websocket.create_connection(
        "wss://api.openai.com/v1/realtime?model=" + quote(model, safe=""), timeout=30,
        header=["Authorization: Bearer " + key], suppress_origin=True,
    )
    chunks = []
    deadline = time.monotonic() + 240

    def send(event):
        socket.send(json.dumps(event, ensure_ascii=False))

    def receive_until(wanted):
        while time.monotonic() < deadline:
            event = json.loads(socket.recv())
            kind = event.get("type")
            if kind == "error":
                error_code = event.get("error", {}).get("code", "inconnu")
                raise RuntimeError(f"OpenAI Audio a refusé la requête ({error_code}).")
            if kind == "response.output_audio.delta":
                chunks.append(base64.b64decode(event["delta"], validate=True))
            if kind == wanted:
                return event
        raise RuntimeError("Le délai de génération vocale est dépassé.")

    try:
        receive_until("session.created")
        send({"type": "session.update", "session": {"type": "realtime", "model": model,
              "output_modalities": ["audio"], "instructions":
              "Lis exactement le texte fourni en français. N’ajoute aucune introduction, réponse ou commentaire. " + direction,
              "audio": {"input": {"turn_detection": None}, "output": {
                  "format": {"type": "audio/pcm", "rate": 24000}, "voice": voice}}}})
        receive_until("session.updated")
        send({"type": "conversation.item.create", "item": {"type": "message", "role": "user",
              "content": [{"type": "input_text", "text": text}]}})
        send({"type": "response.create", "response": {"output_modalities": ["audio"]}})
        result = receive_until("response.done")
        if result.get("response", {}).get("status") != "completed" or not chunks:
            raise RuntimeError("La génération vocale est incomplète ; la prise précédente est conservée.")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".partial.wav")
        with wave.open(str(temporary), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"".join(chunks))
        temporary.replace(output)
    finally:
        socket.close()
