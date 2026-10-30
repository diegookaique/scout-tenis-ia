"""Agente Scout de Tênis IA com a Gemini API (Google), que tem plano gratuito.

Mesmo loop, mesmas tools e mesma trava de SQL do AgenteTenis (Claude). Muda só o
formato das mensagens: o Gemini usa function_call / function_response.
"""

import os
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from src.agente import MAX_ITERACOES, MAX_TOKENS, executar_tool, novo_resultado, registrar
from src.prompts import montar_system_prompt
from src.tools import TOOLS_SCHEMA

# Apelido para o Flash-Lite mais recente: no plano gratuito é o que menos fica sobrecarregado
MODELO_PADRAO = "gemini-flash-lite-latest"
# Tentados em ordem quando o modelo principal responde 5xx (alta demanda, tempo esgotado)
MODELOS_RESERVA = ("gemini-3.5-flash-lite", "gemini-flash-latest")


def declaracoes_tools() -> list[types.FunctionDeclaration]:
    """Converte o TOOLS_SCHEMA (formato Anthropic) em declarações de função do Gemini."""
    return [
        types.FunctionDeclaration(
            name=tool["name"], description=tool["description"], parameters_json_schema=tool["input_schema"]
        )
        for tool in TOOLS_SCHEMA
    ]


class AgenteGemini:
    """Responde perguntas sobre tênis chamando as tools até chegar à resposta final."""

    def __init__(self, modelo: str | None = None, client: genai.Client | None = None):
        self.client = client or genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.modelo = modelo or os.getenv("GEMINI_MODEL", MODELO_PADRAO)
        self.reservas = [m for m in MODELOS_RESERVA if m != self.modelo]
        self.system = montar_system_prompt()
        self.tools = [types.Tool(function_declarations=declaracoes_tools())]

    def perguntar(self, pergunta: str, historico: list[Any] | None = None) -> dict[str, Any]:
        """Roda o loop de tool use. Mesma entrada e saída de AgenteTenis.perguntar."""
        historico = historico or []
        conteudos = [*historico, types.Content(role="user", parts=[types.Part.from_text(text=pergunta)])]
        resultado = novo_resultado(historico)
        # Lista local (o agente é compartilhado entre sessões do app): se um modelo de
        # reserva assumir, ele segue até o fim da pergunta, sem misturar modelos no raciocínio
        modelos = [self.modelo, *self.reservas]

        for iteracao in range(1, MAX_ITERACOES + 1):
            resultado["n_iteracoes"] = iteracao
            # Na última volta, as tools ficam indisponíveis para forçar a resposta final
            resposta, usado = self._chamar_modelo(conteudos, iteracao < MAX_ITERACOES, modelos)
            if usado != modelos[0]:
                registrar(resultado, "aviso", texto=f"{modelos[0]} sobrecarregado; usando {usado}")
                modelos = modelos[modelos.index(usado):]
            _somar_uso(resultado["uso"], resposta.usage_metadata)
            candidato = resposta.candidates[0] if resposta.candidates else None
            partes = (candidato.content.parts or []) if candidato and candidato.content else []
            texto = _extrair_texto(partes)
            chamadas = [p.function_call for p in partes if p.function_call]

            if chamadas:
                # O conteúdo vai inteiro para o histórico: preserva as assinaturas de raciocínio
                conteudos.append(candidato.content)
                if texto:
                    registrar(resultado, "pensamento", texto=texto)
                respostas = [self._executar_tool(chamada, resultado) for chamada in chamadas]
                conteudos.append(types.Content(role="user", parts=respostas))
                continue

            motivo = candidato.finish_reason if candidato else None
            if motivo == types.FinishReason.STOP and texto:
                conteudos.append(candidato.content)
                resultado["resposta_texto"] = texto
                resultado["historico"] = conteudos
            else:
                # bloqueio, limite de tokens etc.: a rodada é descartada do histórico
                resultado["resposta_texto"] = _mensagem_parada(motivo, texto)
                registrar(resultado, "aviso", texto=f"finish_reason={motivo}")
            return resultado

        return resultado  # inalcançável: a última volta sempre termina sem tools

    # ------------------------------------------------------------ chamada à API

    def _chamar_modelo(
        self, conteudos: list[types.Content], permitir_tools: bool, modelos: list[str]
    ) -> tuple[Any, str]:
        """Tenta os modelos em ordem; devolve (resposta, modelo que respondeu)."""
        modo = "AUTO" if permitir_tools else "NONE"
        config = types.GenerateContentConfig(
            system_instruction=self.system,
            tools=self.tools,
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode=modo)),
            # O loop é nosso: o SDK não deve executar funções sozinho
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=MAX_TOKENS,
        )
        for n, modelo in enumerate(modelos):
            try:
                resposta = self.client.models.generate_content(model=modelo, contents=conteudos, config=config)
                return resposta, modelo
            except (errors.ServerError, httpx.TimeoutException):
                if n == len(modelos) - 1:  # nenhum modelo disponível: o app mostra o aviso
                    raise
        raise AssertionError("inalcançável")

    # ------------------------------------------------------------ execução das tools

    def _executar_tool(self, chamada: types.FunctionCall, resultado: dict[str, Any]) -> types.Part:
        """Executa um function_call e devolve a parte function_response correspondente."""
        entrada = {k: _inteiro_se_possivel(v) for k, v in (chamada.args or {}).items()}
        conteudo, erro = executar_tool(chamada.name, entrada, resultado)
        resposta = {"erro": conteudo} if erro else {"resultado": conteudo}
        return types.Part(function_response=types.FunctionResponse(id=chamada.id, name=chamada.name, response=resposta))


def _inteiro_se_possivel(valor: Any) -> Any:
    """Ids podem chegar como 104925.0; as tools esperam int."""
    return int(valor) if isinstance(valor, float) and valor.is_integer() else valor


def _extrair_texto(partes: list[types.Part]) -> str:
    return "\n".join(p.text for p in partes if p.text and not p.thought).strip()


def _somar_uso(uso: dict[str, int], metadados: Any) -> None:
    if metadados is None:
        return
    uso["entrada"] += metadados.prompt_token_count or 0
    uso["saida"] += (metadados.candidates_token_count or 0) + (metadados.thoughts_token_count or 0)
    uso["cache_lido"] += metadados.cached_content_token_count or 0


def _mensagem_parada(motivo: Any, texto: str) -> str:
    motivos = {
        None: "O modelo não pôde responder a esta pergunta.",
        types.FinishReason.MAX_TOKENS: "A resposta ficou longa demais e foi interrompida.",
        types.FinishReason.SAFETY: "O modelo não pôde responder a esta pergunta.",
        types.FinishReason.MALFORMED_FUNCTION_CALL: "O modelo montou uma chamada de ferramenta inválida.",
    }
    aviso = motivos.get(motivo, f"A resposta terminou de forma inesperada ({motivo}).")
    return f"{texto}\n\n⚠️ {aviso} Tente reformular a pergunta.".strip()
