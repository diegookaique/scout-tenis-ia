"""Testes da escolha do provedor de IA e das mensagens de erro (sem chamar APIs)."""

import anthropic
import httpx
import pytest
from google.genai import errors

from src.provedores import descrever_erro, escolher_provedor

GEMINI, CLAUDE = "GEMINI_API_KEY", "ANTHROPIC_API_KEY"


@pytest.mark.parametrize(("chaves", "preferido", "esperado"), [
    ({}, "", ("demo", "")),
    ({GEMINI: "sua-chave-aqui", CLAUDE: "  "}, "", ("demo", "")),
    ({GEMINI: "g-123"}, "", ("gemini", "g-123")),
    ({CLAUDE: "c-123"}, "", ("claude", "c-123")),
    ({GEMINI: "g-123", CLAUDE: "c-123"}, "", ("gemini", "g-123")),  # o gratuito tem prioridade
    ({GEMINI: "g-123", CLAUDE: "c-123"}, "Claude", ("claude", "c-123")),
    ({GEMINI: "g-123"}, "claude", ("demo", "")),  # provedor forçado sem chave
    ({GEMINI: " g-123 "}, "outro", ("gemini", "g-123")),  # valor desconhecido é ignorado
])
def test_escolher_provedor(chaves, preferido, esperado):
    assert escolher_provedor(chaves, preferido) == esperado


def _erro_gemini(codigo: int, mensagem: str = "") -> errors.APIError:
    return errors.APIError(codigo, {"error": {"code": codigo, "message": mensagem, "status": ""}})


@pytest.mark.parametrize(("erro", "trecho"), [
    (_erro_gemini(429, "Resource exhausted"), "limite gratuito"),
    (_erro_gemini(400, "API key not valid. Please pass a valid API key."), "GEMINI_API_KEY"),
    (_erro_gemini(404, "models/x is not found"), "GEMINI_MODEL"),
    (_erro_gemini(503, "high demand"), "sobrecarregados"),
    (_erro_gemini(500, "internal"), "sobrecarregados"),
    (_erro_gemini(418, "?"), "erro 418"),
])
def test_erros_do_gemini(erro, trecho):
    assert trecho in descrever_erro(erro)


def test_erro_de_chave_da_claude():
    resposta = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com"))
    erro = anthropic.AuthenticationError("chave inválida", response=resposta, body=None)
    assert "ANTHROPIC_API_KEY" in descrever_erro(erro)


def test_tempo_esgotado():
    assert "demorou demais" in descrever_erro(httpx.ReadTimeout("tempo esgotado"))


def test_erro_comum_nao_e_de_api():
    assert descrever_erro(ValueError("x")) is None
