"""Escolha do provedor de IA: Gemini (tem plano gratuito), Claude ou modo demonstração.

As chaves vêm de GEMINI_API_KEY e ANTHROPIC_API_KEY (local: .env; deploy: st.secrets).
PROVEDOR=gemini ou PROVEDOR=claude força um deles; sem PROVEDOR, o Gemini tem prioridade.
"""

import os
from typing import Any

CHAVE_EXEMPLO = "sua-chave-aqui"
VARIAVEIS = {"gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}
NOMES = {"gemini": "Gemini API (Google)", "claude": "Claude API (Anthropic)", "demo": "modo demonstração"}


def chave_valida(valor: str | None) -> str:
    """A chave sem espaços; vazia se não existir ou ainda for o texto de exemplo."""
    valor = (valor or "").strip()
    return "" if valor == CHAVE_EXEMPLO else valor


def escolher_provedor(chaves: dict[str, str], preferido: str = "") -> tuple[str, str]:
    """Devolve (provedor, chave). Sem chave válida, devolve ("demo", "")."""
    preferido = preferido.strip().lower()
    ordem = [preferido] if preferido in VARIAVEIS else ["gemini", "claude"]
    for provedor in ordem:
        chave = chave_valida(chaves.get(VARIAVEIS[provedor]))
        if chave:
            return provedor, chave
    return "demo", ""


def chaves_do_ambiente() -> dict[str, str]:
    return {var: os.getenv(var, "") for var in VARIAVEIS.values()}


def criar_agente(provedor: str, chave: str) -> Any:
    """Instancia o agente do provedor; todos têm o mesmo método perguntar()."""
    if provedor == "gemini":
        from google import genai
        from google.genai import types

        from src.agente_gemini import AgenteGemini

        # Sem novas tentativas no mesmo modelo: em caso de sobrecarga o agente já troca de modelo
        opcoes = types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1))
        return AgenteGemini(client=genai.Client(api_key=chave, http_options=opcoes))
    if provedor == "claude":
        import anthropic

        from src.agente import AgenteTenis

        return AgenteTenis(client=anthropic.Anthropic(api_key=chave))
    from src.demo import AgenteDemo

    return AgenteDemo()


def descrever_erro(erro: Exception) -> str | None:
    """Mensagem amigável para uma falha de API; None se o erro não veio de uma API."""
    import anthropic
    import httpx
    from google.genai import errors as erros_gemini

    if isinstance(erro, httpx.TimeoutException):
        return "A IA demorou demais para responder. Tente de novo em instantes."
    if isinstance(erro, erros_gemini.APIError):
        texto = str(erro)
        if erro.code == 429:
            return ("O limite gratuito da Gemini API foi atingido por agora. "
                    "Espere um minuto e tente de novo.")
        if erro.code in (401, 403) or "API_KEY_INVALID" in texto or "API key not valid" in texto:
            return "A chave da Gemini API foi recusada. Confira o valor de GEMINI_API_KEY."
        if erro.code == 404:
            return "O modelo do Gemini não foi encontrado. Confira o valor de GEMINI_MODEL."
        if erro.code in (500, 503, 504):
            return ("Os modelos gratuitos do Gemini estão sobrecarregados agora. "
                    "Tente de novo em instantes.")
        return f"A Gemini API não respondeu agora (erro {erro.code}). Tente de novo em instantes."
    if isinstance(erro, anthropic.AuthenticationError):
        return "A chave da Claude API foi recusada. Confira o valor de ANTHROPIC_API_KEY."
    if isinstance(erro, anthropic.APIError):
        return f"A Claude API não respondeu agora ({type(erro).__name__}). Tente de novo em instantes."
    return None
