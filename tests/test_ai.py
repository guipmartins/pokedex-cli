import base64
import io

import pytest
from conftest import POKEMON, SPECIES
from PIL import Image

from pokedex.ai import (
    AIError,
    AnthropicProvider,
    Message,
    OpenAIProvider,
    PokedexAI,
    load_dotenv,
    parse_identification,
    pokemon_facts,
    prepare_image,
    provider_from_env,
)
from pokedex.cache import DiskCache
from pokedex.models import Pokemon, Species


@pytest.fixture
def pikachu():
    return Pokemon.from_api(POKEMON["pikachu"]), Species.from_api(SPECIES["pikachu"])


def png(size=(2000, 1000), mode="RGBA") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (200, 30, 30, 255) if mode == "RGBA" else (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def clean_env(monkeypatch):
    for key in ("AI_PROVIDER", "AI_MODEL", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_no_key_means_ai_disabled(clean_env):
    assert provider_from_env() is None


def test_detects_provider_from_key(clean_env):
    clean_env.setenv("OPENAI_API_KEY", "sk-test")
    provider = provider_from_env()
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-6-luna"


def test_explicit_provider_and_model(clean_env):
    clean_env.setenv("OPENAI_API_KEY", "sk-test")
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant")
    clean_env.setenv("AI_PROVIDER", "anthropic")
    clean_env.setenv("AI_MODEL", "claude-sonnet-5-5")
    provider = provider_from_env()
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-5-5"


def test_load_dotenv_does_not_override(tmp_path, clean_env):
    env = tmp_path / ".env"
    env.write_text('# comentário\nOPENAI_API_KEY="sk-file"\nAI_MODEL=modelo-x\n', encoding="utf-8")
    clean_env.setenv("AI_MODEL", "ja-definido")
    load_dotenv(env)
    import os

    assert os.environ["OPENAI_API_KEY"] == "sk-file"
    assert os.environ["AI_MODEL"] == "ja-definido"


def test_facts_include_weaknesses_in_portuguese(pikachu):
    facts = pokemon_facts(*pikachu)
    assert facts["tipos"] == ["Elétrico"]
    assert facts["fraco_contra"] == ["Terrestre"]
    assert facts["stats_base"]["Velocidade"] == 90


def test_anthropic_request_format(ai_server, ai_client, pikachu, tmp_path):
    engine = PokedexAI(
        AnthropicProvider("sk-ant", "claude-haiku-5-5", ai_client), DiskCache(tmp_path)
    )
    text = engine.entry(*pikachu)
    assert text.startswith("Pikachu")
    req = ai_server.requests[0]
    assert req["url"] == "https://api.anthropic.com/v1/messages"
    assert req["headers"]["x-api-key"] == "sk-ant"
    assert req["body"]["model"] == "claude-haiku-5-5"
    assert "Pokédex" in req["body"]["system"]
    assert "Terrestre" in req["body"]["messages"][0]["content"]


def test_entry_is_cached(ai_server, ai_client, pikachu, tmp_path):
    engine = PokedexAI(OpenAIProvider("sk", "gpt-6-luna", ai_client), DiskCache(tmp_path))
    engine.entry(*pikachu)
    engine.entry(*pikachu)
    assert len(ai_server.requests) == 1


def test_openai_ask_sends_history(ai_server, ai_client, pikachu, tmp_path):
    engine = PokedexAI(OpenAIProvider("sk", "gpt-6-luna", ai_client), DiskCache(tmp_path))
    history = [Message("user", "oi"), Message("assistant", "olá, treinador")]
    engine.ask(*pikachu, "Qual o melhor golpe?", history)
    body = ai_server.requests[0]["body"]
    assert body["messages"][0]["role"] == "system"
    assert [m["content"] for m in body["messages"][1:]] == [
        "oi",
        "olá, treinador",
        "Qual o melhor golpe?",
    ]
    assert ai_server.requests[0]["headers"]["authorization"] == "Bearer sk"


def test_identify_sends_resized_image(ai_server, ai_client, tmp_path):
    ai_server.reply = (
        '```json\n{"pokemon": "Pikachu", "confianca": 0.93, "motivo": "Rato amarelo"}\n```'
    )
    engine = PokedexAI(AnthropicProvider("k", "m", ai_client), DiskCache(tmp_path))
    result = engine.identify(png())
    assert result == {"pokemon": "pikachu", "confianca": 0.93, "motivo": "Rato amarelo"}

    block = ai_server.requests[0]["body"]["messages"][0]["content"][0]
    assert block["type"] == "image" and block["source"]["media_type"] == "image/jpeg"
    sent = Image.open(io.BytesIO(base64.b64decode(block["source"]["data"])))
    assert max(sent.size) == 1024


def test_openai_image_format(ai_server, ai_client, tmp_path):
    ai_server.reply = '{"pokemon": null, "confianca": 0, "motivo": "Só um gato"}'
    engine = PokedexAI(OpenAIProvider("k", "m", ai_client), DiskCache(tmp_path))
    assert engine.identify(png((50, 50), "RGB"))["pokemon"] is None
    parts = ai_server.requests[0]["body"]["messages"][1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize("status", [401, 429, 500])
def test_api_errors_become_friendly(ai_server, ai_client, pikachu, tmp_path, status):
    ai_server.status = status
    engine = PokedexAI(OpenAIProvider("k", "m", ai_client), DiskCache(tmp_path))
    with pytest.raises(AIError):
        engine.ask(*pikachu, "oi")


def test_prepare_image_rejects_garbage():
    with pytest.raises(AIError):
        prepare_image(b"nada a ver")


def test_parse_identification_clamps_confidence():
    assert parse_identification('{"pokemon": "mew", "confianca": 7}')["confianca"] == 1.0
    with pytest.raises(AIError):
        parse_identification("não sei")
