"""Integração com IA (Anthropic Claude ou OpenAI) para a Pokédex.

Três usos:
- narrar a entrada da Pokédex em português, no tom do aparelho;
- responder perguntas sobre o Pokémon que está na tela;
- identificar um Pokémon a partir de uma foto ou desenho.

As chamadas são feitas direto na API HTTP com httpx, sem SDK, para manter as
dependências enxutas e facilitar os testes com um transporte falso.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from pokedex.cache import DiskCache
from pokedex.models import Pokemon, Species
from pokedex.type_chart import defensive_profile, type_name

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-6-luna",
}
MAX_IMAGE_SIDE = 1024


class AIError(Exception):
    """Erro com mensagem amigável vindo da camada de IA."""


def load_dotenv(path: str | Path = ".env") -> None:
    """Lê um arquivo .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Message:
    role: str  # "user" ou "assistant"
    content: str


class AIProvider:
    name = "base"

    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self._client = client or httpx.Client(timeout=60.0)

    def complete(
        self,
        system: str,
        messages: list[Message],
        image: tuple[bytes, str] | None = None,
        max_tokens: int = 500,
    ) -> str:
        raise NotImplementedError

    def _post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict:
        try:
            response = self._client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise AIError(f"Não consegui falar com a IA ({self.name}): {exc}") from exc
        if response.status_code in (401, 403):
            raise AIError(f"A chave da API {self.name} foi recusada. Confira o arquivo .env.")
        if response.status_code == 429:
            raise AIError("Limite de uso da IA atingido. Tente de novo em instantes.")
        if response.status_code >= 400:
            detail = response.text[:300]
            raise AIError(f"A IA respondeu com erro {response.status_code}: {detail}")
        return response.json()


class AnthropicProvider(AIProvider):
    name = "anthropic"
    url = "https://api.anthropic.com/v1/messages"

    def complete(self, system, messages, image=None, max_tokens=500):
        payload_messages: list[dict[str, Any]] = [
            {"role": m.role, "content": m.content} for m in messages
        ]
        if image:
            data, media_type = image
            last = payload_messages[-1]
            last["content"] = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.b64encode(data).decode(),
                    },
                },
                {"type": "text", "text": last["content"]},
            ]
        data = self._post(
            self.url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload={
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": payload_messages,
            },
        )
        return "".join(b.get("text", "") for b in data.get("content", [])).strip()


class OpenAIProvider(AIProvider):
    name = "openai"
    url = "https://api.openai.com/v1/chat/completions"

    def complete(self, system, messages, image=None, max_tokens=500):
        payload_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        payload_messages += [{"role": m.role, "content": m.content} for m in messages]
        if image:
            data, media_type = image
            last = payload_messages[-1]
            url = f"data:{media_type};base64,{base64.b64encode(data).decode()}"
            last["content"] = [
                {"type": "text", "text": last["content"]},
                {"type": "image_url", "image_url": {"url": url}},
            ]
        data = self._post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload={
                "model": self.model,
                "max_completion_tokens": max_tokens,
                "messages": payload_messages,
            },
        )
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError) as exc:
            raise AIError("Resposta inesperada da IA.") from exc


PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider}


def provider_from_env(client: httpx.Client | None = None) -> AIProvider | None:
    """Escolhe o provedor pelas variáveis de ambiente. Sem chave, a IA fica desligada."""
    chosen = os.environ.get("AI_PROVIDER", "").strip().lower()
    keys = {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        "openai": os.environ.get("OPENAI_API_KEY", "").strip(),
    }
    if not chosen:
        chosen = next((name for name, key in keys.items() if key), "")
    if chosen not in PROVIDERS or not keys.get(chosen):
        return None
    model = os.environ.get("AI_MODEL", "").strip() or DEFAULT_MODELS[chosen]
    return PROVIDERS[chosen](keys[chosen], model, client=client)


# ------------------------------------------------------------------- prompts
def pokemon_facts(pokemon: Pokemon, species: Species | None) -> dict[str, Any]:
    """Os fatos que a IA recebe. Assim ela narra a partir de dados reais, sem inventar."""
    profile = defensive_profile(pokemon.types)
    return {
        "numero": pokemon.id,
        "nome": pokemon.display_name,
        "tipos": [type_name(t) for t in pokemon.types],
        "especie": species.genus if species else None,
        "altura_m": pokemon.height_m,
        "peso_kg": pokemon.weight_kg,
        "habilidades": [
            f"{a.replace('-', ' ')}{' (oculta)' if hidden else ''}"
            for a, hidden in pokemon.abilities
        ],
        "stats_base": {s.label: s.value for s in pokemon.stats},
        "total_stats": pokemon.total,
        "fraco_contra": [type_name(t) for t, m in profile.items() if m > 1],
        "resiste_a": [type_name(t) for t, m in profile.items() if 0 < m < 1],
        "imune_a": [type_name(t) for t, m in profile.items() if m == 0],
        "geracao": species.generation if species else None,
        "lendario": species.is_legendary if species else False,
        "mitico": species.is_mythical if species else False,
        "texto_oficial_ingles": species.flavor_text if species else None,
    }


ENTRY_SYSTEM = """Você é a voz de uma Pokédex, a enciclopédia eletrônica dos treinadores.
Escreva a entrada do Pokémon em português do Brasil, no tom clássico e direto da Pokédex do anime:
comece com "<Nome>, o Pokémon <categoria>." e depois 2 ou 3 frases sobre comportamento,
habitat ou curiosidades. No máximo 70 palavras. Texto corrido, sem listas, sem markdown,
sem números de stats. Baseie-se nos fatos fornecidos e no conhecimento consolidado da franquia;
se não tiver certeza de algo, não afirme."""

ASK_SYSTEM = """Você é uma Pokédex inteligente conversando com um treinador.
Responda em português do Brasil, de forma curta (até 120 palavras), útil e simpática.
Use os fatos do Pokémon fornecidos como fonte principal para números, tipos e fraquezas.
Para estratégia de batalha, golpes e curiosidades, use o conhecimento consolidado da franquia
e deixe claro quando algo depende do jogo ou da geração. Sem markdown pesado: no máximo
listas simples com hífen. Se a pergunta não tiver nada a ver com Pokémon, diga educadamente
que você é uma Pokédex e só fala de Pokémon."""

IDENTIFY_SYSTEM = """Você identifica Pokémon em imagens (fotos, prints, desenhos, pelúcias,
cartas, cosplay). Responda SOMENTE com um JSON, sem texto em volta, neste formato:
{"pokemon": "<nome em inglês no formato da PokeAPI, minúsculo, com hífen; ex.: mr-mime>",
 "confianca": <número de 0 a 1>,
 "motivo": "<uma frase curta em português explicando o que você reconheceu>"}
Se não houver Pokémon reconhecível, use "pokemon": null."""


class PokedexAI:
    def __init__(self, provider: AIProvider, cache: DiskCache | None = None) -> None:
        self.provider = provider
        self.cache = cache or DiskCache()

    @property
    def label(self) -> str:
        return f"{self.provider.name} · {self.provider.model}"

    def entry(self, pokemon: Pokemon, species: Species | None) -> str:
        # Narração é sempre a mesma para o mesmo Pokémon: cachear economiza dinheiro.
        key = f"ai-entry:v1:{self.provider.name}:{self.provider.model}:{pokemon.name}"
        cached = self.cache.get_json(key)
        if cached:
            return cached["text"]
        facts = json.dumps(pokemon_facts(pokemon, species), ensure_ascii=False)
        text = self.provider.complete(
            ENTRY_SYSTEM, [Message("user", f"Fatos do Pokémon:\n{facts}")], max_tokens=300
        )
        if not text:
            raise AIError("A IA devolveu uma resposta vazia.")
        self.cache.set_json(key, {"text": text})
        return text

    def ask(
        self,
        pokemon: Pokemon,
        species: Species | None,
        question: str,
        history: list[Message] | None = None,
    ) -> str:
        question = question.strip()[:500]
        if not question:
            raise AIError("Faça uma pergunta.")
        facts = json.dumps(pokemon_facts(pokemon, species), ensure_ascii=False)
        system = f"{ASK_SYSTEM}\n\nPokémon na tela agora:\n{facts}"
        messages = [m for m in (history or []) if m.role in ("user", "assistant")][-6:]
        messages.append(Message("user", question))
        return self.provider.complete(system, messages, max_tokens=400)

    def identify(self, image_bytes: bytes) -> dict[str, Any]:
        image = prepare_image(image_bytes)
        raw = self.provider.complete(
            IDENTIFY_SYSTEM,
            [Message("user", "Qual Pokémon aparece nesta imagem?")],
            image=image,
            max_tokens=200,
        )
        return parse_identification(raw)


def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Reduz a imagem para no máximo 1024px e converte para JPEG (menos tokens, menos custo)."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise AIError("Não consegui abrir essa imagem. Envie um PNG, JPG ou WEBP.") from exc
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.getchannel("A"))
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue(), "image/jpeg"


def parse_identification(raw: str) -> dict[str, Any]:
    """Extrai o JSON da resposta, mesmo que venha com ```json ou texto em volta."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise AIError("A IA não conseguiu identificar a imagem.")
    try:
        data = json.loads(match.group(0))
    except ValueError as exc:
        raise AIError("A IA respondeu num formato inesperado.") from exc
    name = data.get("pokemon")
    try:
        confidence = float(data.get("confianca") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "pokemon": str(name).strip().lower() if name else None,
        "confianca": max(0.0, min(1.0, confidence)),
        "motivo": str(data.get("motivo") or ""),
    }
