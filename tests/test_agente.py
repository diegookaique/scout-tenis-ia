"""Testes do loop do agente com um cliente falso (não chama a API nem gasta tokens)."""

from types import SimpleNamespace

import pytest

from src.agente import MAX_ITERACOES, AgenteTenis
from src.db import CAMINHO_BANCO

pytestmark = pytest.mark.skipif(not CAMINHO_BANCO.exists(), reason="tenis.duckdb não encontrado")


def texto(t: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=t)


def tool_use(id_: str, nome: str, entrada: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=nome, input=entrada)


def resposta(stop_reason: str, *blocos: SimpleNamespace) -> SimpleNamespace:
    uso = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=50,
                          cache_creation_input_tokens=0)
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocos), usage=uso)


class ClienteFalso:
    """Devolve as respostas roteirizadas em ordem e guarda cada requisição."""

    def __init__(self, *respostas: SimpleNamespace):
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # cópia: o agente continua acrescentando mensagens à mesma lista depois
        self.chamadas.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.respostas.pop(0) if self.respostas else resposta("end_turn", texto("fim"))


def test_loop_executa_tools_e_devolve_resposta():
    cliente = ClienteFalso(
        resposta("tool_use", texto("Vou buscar o jogador."), tool_use("t1", "buscar_jogador", {"nome": "djokovic"})),
        resposta("tool_use", tool_use("t2", "consultar_sql", {"sql": "SELECT count(*) FROM partidas"})),
        resposta("end_turn", texto("São 79.299 partidas.")),
    )
    r = AgenteTenis(client=cliente).perguntar("Quantas partidas há?")

    assert r["resposta_texto"] == "São 79.299 partidas."
    assert r["n_iteracoes"] == 3
    assert [s["sql"] for s in r["sqls_executados"]] == ["SELECT count(*) FROM partidas"]
    assert r["uso"]["entrada"] == 300
    # O resultado real da tool volta para o modelo, no mesmo id do tool_use
    tool_result = cliente.chamadas[1]["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and "104925" in tool_result["content"]
    # Histórico: pergunta, 3 respostas do assistente e 2 mensagens de tool_result
    assert len(r["historico"]) == 6


def test_erro_de_sql_volta_como_is_error():
    cliente = ClienteFalso(
        resposta("tool_use", tool_use("t1", "consultar_sql", {"sql": "DROP TABLE partidas"})),
        resposta("end_turn", texto("Não posso fazer isso.")),
    )
    r = AgenteTenis(client=cliente).perguntar("Apague a tabela")

    tool_result = cliente.chamadas[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True
    assert r["sqls_executados"][0]["erro"]


def test_autocorrecao_apos_sql_com_erro():
    cliente = ClienteFalso(
        resposta("tool_use", tool_use("t1", "consultar_sql", {"sql": "SELECT count(*) FROM partida"})),
        resposta("tool_use", tool_use("t2", "consultar_sql", {"sql": "SELECT count(*) AS n FROM partidas"})),
        resposta("end_turn", texto("São 79.299 partidas.")),
    )
    r = AgenteTenis(client=cliente).perguntar("Quantas partidas há?")

    # A mensagem real do DuckDB chega ao modelo, que reenvia a consulta corrigida
    erro = cliente.chamadas[1]["messages"][-1]["content"][0]
    assert erro["is_error"] is True and "partida" in erro["content"]
    acerto = cliente.chamadas[2]["messages"][-1]["content"][0]
    assert acerto["is_error"] is False and "79299" in acerto["content"]
    assert [bool(s["erro"]) for s in r["sqls_executados"]] == [True, False]
    assert r["resposta_texto"] == "São 79.299 partidas."


def test_grafico_fica_no_resultado_e_nao_volta_para_o_modelo():
    dados = [{"sup": "Clay", "v": 10}, {"sup": "Hard", "v": 20}]
    cliente = ClienteFalso(
        resposta("tool_use", tool_use("t1", "gerar_grafico",
                                      {"dados": dados, "tipo": "barra", "x": "sup", "y": "v", "titulo": "T"})),
        resposta("end_turn", texto("Pronto.")),
    )
    r = AgenteTenis(client=cliente).perguntar("Gráfico")

    assert len(r["graficos"]) == 1
    assert "Gráfico gerado" in cliente.chamadas[1]["messages"][-1]["content"][0]["content"]


def test_limite_de_iteracoes_desliga_tools_na_ultima_volta():
    loop_infinito = [resposta("tool_use", tool_use(f"t{i}", "listar_tabelas", {})) for i in range(MAX_ITERACOES - 1)]
    cliente = ClienteFalso(*loop_infinito, resposta("end_turn", texto("Resposta final.")))
    r = AgenteTenis(client=cliente).perguntar("?")

    assert r["n_iteracoes"] == MAX_ITERACOES
    assert cliente.chamadas[-1]["tool_choice"] == {"type": "none"}
    assert r["resposta_texto"] == "Resposta final."


def test_parada_anormal_nao_altera_historico():
    cliente = ClienteFalso(resposta("refusal"))
    r = AgenteTenis(client=cliente).perguntar("?", historico=[])

    assert r["historico"] == []
    assert "não pôde responder" in r["resposta_texto"]


def test_requisicao_usa_modelo_cache_e_fallback():
    cliente = ClienteFalso(resposta("end_turn", texto("oi")))
    agente = AgenteTenis(modelo="claude-sonnet-5-5", client=cliente)
    agente.perguntar("oi")

    chamada = cliente.chamadas[0]
    assert chamada["model"] == "claude-sonnet-5-5"
    assert chamada["cache_control"] == {"type": "ephemeral"}
    assert chamada["fallbacks"] == "default"
    assert "<esquema>" in chamada["system"]
