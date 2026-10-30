"""Agente Scout de Tênis IA: loop de tool use com a Claude API.

O agente com a Gemini API (plano gratuito) fica em src/agente_gemini.py e reaproveita
as funções comuns daqui. Uso no terminal (escolhe o provedor pelas chaves do .env):
    python -m src.agente
"""

import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from src.prompts import montar_system_prompt
from src.tools import FUNCOES, TOOLS_SCHEMA

load_dotenv()

MODELO_PADRAO = "claude-sonnet-5-5"
MAX_ITERACOES = 8
MAX_TOKENS = 16000
# Esforço de raciocínio: "medium" é o ponto de partida recomendado para uso de várias tools
ESFORCO = os.getenv("ANTHROPIC_EFFORT", "medium")
# Se o modelo recusar por segurança, a API refaz a chamada num modelo alternativo
MODELOS_COM_FALLBACK = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}
BETA_FALLBACK = "server-side-fallback-2026-07-01"

log = logging.getLogger("agente")


class AgenteTenis:
    """Responde perguntas sobre tênis chamando as tools até chegar à resposta final."""

    def __init__(self, modelo: str | None = None, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()
        self.modelo = modelo or os.getenv("ANTHROPIC_MODEL", MODELO_PADRAO)
        self.system = montar_system_prompt()

    def perguntar(self, pergunta: str, historico: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Roda o loop de tool use para uma pergunta.

        `historico` são as mensagens das perguntas anteriores (o campo "historico"
        devolvido pela chamada anterior). Retorna {resposta_texto, sqls_executados,
        graficos, n_iteracoes, passos, uso, historico}.
        """
        historico = historico or []
        mensagens = [*historico, {"role": "user", "content": pergunta}]
        resultado = novo_resultado(historico)

        for iteracao in range(1, MAX_ITERACOES + 1):
            resultado["n_iteracoes"] = iteracao
            # Na última volta, as tools ficam indisponíveis para forçar a resposta final
            ultima = iteracao == MAX_ITERACOES
            resposta = self._chamar_modelo(mensagens, permitir_tools=not ultima)
            self._somar_uso(resultado["uso"], resposta.usage)
            texto = _extrair_texto(resposta)
            mensagens.append({"role": "assistant", "content": resposta.content})

            if resposta.stop_reason == "tool_use":
                if texto:
                    registrar(resultado, "pensamento", texto=texto)
                resultados_tools = [
                    self._executar_tool(bloco, resultado)
                    for bloco in resposta.content
                    if bloco.type == "tool_use"
                ]
                mensagens.append({"role": "user", "content": resultados_tools})
                continue

            if resposta.stop_reason in ("end_turn", "stop_sequence"):
                resultado["resposta_texto"] = texto
                resultado["historico"] = mensagens
            else:
                # max_tokens, refusal etc.: a rodada é descartada do histórico
                resultado["resposta_texto"] = _mensagem_parada(resposta.stop_reason, texto)
                registrar(resultado, "aviso", texto=f"stop_reason={resposta.stop_reason}")
            return resultado

        return resultado  # inalcançável: a última volta sempre termina sem tools

    # ------------------------------------------------------------ chamada à API

    def _chamar_modelo(self, mensagens: list[dict[str, Any]], permitir_tools: bool) -> Any:
        extras: dict[str, Any] = {}
        if self.modelo in MODELOS_COM_FALLBACK:
            extras = {"betas": [BETA_FALLBACK], "fallbacks": "default"}
        return self.client.beta.messages.create(
            model=self.modelo,
            max_tokens=MAX_TOKENS,
            system=self.system,
            tools=TOOLS_SCHEMA,
            tool_choice={"type": "auto" if permitir_tools else "none"},
            messages=mensagens,
            output_config={"effort": ESFORCO},
            # Cacheia tools + system + histórico: perguntas seguintes custam bem menos
            cache_control={"type": "ephemeral"},
            **extras,
        )

    # ------------------------------------------------------------ execução das tools

    def _executar_tool(self, bloco: Any, resultado: dict[str, Any]) -> dict[str, Any]:
        """Executa um tool_use e devolve o bloco tool_result correspondente."""
        conteudo, erro = executar_tool(bloco.name, dict(bloco.input), resultado)
        return {"type": "tool_result", "tool_use_id": bloco.id, "content": conteudo, "is_error": bool(erro)}

    # ------------------------------------------------------------ uso

    @staticmethod
    def _somar_uso(uso: dict[str, int], usage: Any) -> None:
        uso["entrada"] += usage.input_tokens or 0
        uso["saida"] += usage.output_tokens or 0
        uso["cache_lido"] += usage.cache_read_input_tokens or 0
        uso["cache_gravado"] += usage.cache_creation_input_tokens or 0


# ---------------------------------------------------------------- comum aos provedores


def novo_resultado(historico: list[Any]) -> dict[str, Any]:
    """Estrutura devolvida por perguntar(), igual para Claude, Gemini e o modo demonstração."""
    return {
        "resposta_texto": "",
        "sqls_executados": [],
        "graficos": [],
        "n_iteracoes": 0,
        "passos": [],
        "uso": {"entrada": 0, "saida": 0, "cache_lido": 0, "cache_gravado": 0},
        "historico": historico,
    }


def executar_tool(nome: str, entrada: dict[str, Any], resultado: dict[str, Any]) -> tuple[str, str | None]:
    """Executa uma tool, registra o passo e devolve (conteúdo para o modelo, erro)."""
    try:
        saida = FUNCOES[nome](**entrada)
        erro = _erro_da_saida(saida)
    except Exception as exc:  # o agente recebe o erro e pode se corrigir
        saida, erro = None, f"{type(exc).__name__}: {exc}"

    if nome == "consultar_sql":
        resultado["sqls_executados"].append({"sql": entrada.get("sql", ""), "erro": erro})
    if nome == "gerar_grafico" and not erro:
        resultado["graficos"].append(saida["figura"])
        saida = {"ok": True, "mensagem": "Gráfico gerado e exibido ao usuário."}

    registrar(resultado, "tool", nome=nome, entrada=_resumir_entrada(nome, entrada), erro=erro)
    conteudo = erro if erro else json.dumps(saida, ensure_ascii=False, default=str)
    return conteudo, erro


def registrar(resultado: dict[str, Any], tipo: str, **dados: Any) -> None:
    passo = {"tipo": tipo, "iteracao": resultado["n_iteracoes"], **dados}
    resultado["passos"].append(passo)
    log.info("passo %s", passo)


def _extrair_texto(resposta: Any) -> str:
    return "\n".join(b.text for b in resposta.content if b.type == "text").strip()


def _erro_da_saida(saida: Any) -> str | None:
    """consultar_sql e gerar_grafico sinalizam falha no campo 'erro'."""
    return saida.get("erro") if isinstance(saida, dict) else None


def _resumir_entrada(nome: str, entrada: dict[str, Any]) -> dict[str, Any]:
    """Evita registrar no log a lista inteira de dados de um gráfico."""
    if nome == "gerar_grafico":
        return {k: v for k, v in entrada.items() if k != "dados"} | {"n_dados": len(entrada.get("dados", []))}
    return entrada


def _mensagem_parada(stop_reason: str | None, texto: str) -> str:
    motivos = {
        "max_tokens": "A resposta ficou longa demais e foi interrompida.",
        "refusal": "O modelo não pôde responder a esta pergunta.",
    }
    aviso = motivos.get(stop_reason or "", f"A resposta terminou de forma inesperada ({stop_reason}).")
    return f"{texto}\n\n⚠️ {aviso} Tente reformular a pergunta.".strip()


# ---------------------------------------------------------------- terminal


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "WARNING"))
    from src.provedores import NOMES, chaves_do_ambiente, criar_agente, descrever_erro, escolher_provedor

    provedor, chave = escolher_provedor(chaves_do_ambiente(), os.getenv("PROVEDOR", ""))
    if provedor == "demo":
        print("Nenhuma chave de IA configurada. Abra o arquivo .env e troque 'sua-chave-aqui' "
              "em GEMINI_API_KEY (grátis em aistudio.google.com) ou em ANTHROPIC_API_KEY.")
        return
    agente = criar_agente(provedor, chave)
    print(f"🎾 Scout de Tênis IA ({NOMES[provedor]}, {agente.modelo}). Digite 'sair' para encerrar.\n")
    historico: list[Any] = []
    while True:
        try:
            pergunta = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in ("sair", "exit", "quit"):
            break
        if not pergunta:
            continue
        try:
            r = agente.perguntar(pergunta, historico)
        except Exception as erro:
            mensagem = descrever_erro(erro)
            if mensagem is None:
                raise
            print(f"\n[erro na API] {mensagem}\n")
            continue
        historico = r["historico"]
        for passo in r["passos"]:
            if passo["tipo"] == "tool":
                status = f" ✗ {passo['erro'][:80]}" if passo["erro"] else ""
                print(f"  · {passo['nome']} {json.dumps(passo['entrada'], ensure_ascii=False)[:150]}{status}")
        print(f"\nScout: {r['resposta_texto']}")
        if r["graficos"]:
            print(f"  ({len(r['graficos'])} gráfico(s) gerado(s); visíveis na interface Streamlit)")
        uso = r["uso"]
        print(f"  [{r['n_iteracoes']} iterações · tokens: {uso['entrada']} entrada, "
              f"{uso['saida']} saída, {uso['cache_lido']} do cache]\n")


if __name__ == "__main__":
    main()
