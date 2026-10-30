"""Testes do loop do agente Gemini com um cliente falso (não chama a API)."""

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors, types

from src.agente import MAX_ITERACOES
from src.agente_gemini import MODELOS_RESERVA, AgenteGemini, declaracoes_tools
from src.db import CAMINHO_BANCO
from src.tools import TOOLS_SCHEMA

pytestmark = pytest.mark.skipif(not CAMINHO_BANCO.exists(), reason="tenis.duckdb não encontrado")


def texto(t: str) -> types.Part:
    return types.Part.from_text(text=t)


def chamada(id_: str, nome: str, args: dict) -> types.Part:
    return types.Part(function_call=types.FunctionCall(id=id_, name=nome, args=args))


def resposta(*partes: types.Part, motivo: types.FinishReason = types.FinishReason.STOP) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(partes)), finish_reason=motivo)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=100, candidates_token_count=20),
    )


class ClienteFalso:
    """Devolve as respostas roteirizadas em ordem e guarda cada requisição."""

    def __init__(self, *respostas: types.GenerateContentResponse | Exception):
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []
        self.models = SimpleNamespace(generate_content=self._gerar)

    def _gerar(self, model, contents, config):
        # cópia: o agente continua acrescentando conteúdos à mesma lista depois
        self.chamadas.append({"model": model, "contents": list(contents), "config": config})
        proxima = self.respostas.pop(0) if self.respostas else resposta(texto("fim"))
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


def test_declaracoes_cobrem_todas_as_tools():
    assert [d.name for d in declaracoes_tools()] == [t["name"] for t in TOOLS_SCHEMA]


def test_loop_executa_tools_e_devolve_resposta():
    cliente = ClienteFalso(
        resposta(texto("Vou buscar o jogador."), chamada("c1", "buscar_jogador", {"nome": "djokovic"})),
        resposta(chamada("c2", "consultar_sql", {"sql": "SELECT count(*) FROM partidas"})),
        resposta(texto("São 79.299 partidas.")),
    )
    r = AgenteGemini(modelo="gemini-teste", client=cliente).perguntar("Quantas partidas há?")

    assert r["resposta_texto"] == "São 79.299 partidas."
    assert r["n_iteracoes"] == 3
    assert [s["sql"] for s in r["sqls_executados"]] == ["SELECT count(*) FROM partidas"]
    assert r["uso"]["entrada"] == 300
    assert r["passos"][0] == {"tipo": "pensamento", "iteracao": 1, "texto": "Vou buscar o jogador."}
    # O resultado real da tool volta para o modelo com o mesmo id e nome da chamada
    retorno = cliente.chamadas[1]["contents"][-1].parts[0].function_response
    assert retorno.id == "c1" and retorno.name == "buscar_jogador"
    assert "104925" in retorno.response["resultado"]
    # Histórico: pergunta, 3 respostas do modelo e 2 mensagens de function_response
    assert len(r["historico"]) == 6


def test_erro_de_sql_volta_como_erro_e_agente_corrige():
    cliente = ClienteFalso(
        resposta(chamada("c1", "consultar_sql", {"sql": "DROP TABLE partidas"})),
        resposta(chamada("c2", "consultar_sql", {"sql": "SELECT count(*) AS n FROM partidas"})),
        resposta(texto("Não posso apagar, mas há 79.299 partidas.")),
    )
    r = AgenteGemini(client=cliente).perguntar("Apague a tabela")

    retorno = cliente.chamadas[1]["contents"][-1].parts[0].function_response
    assert "erro" in retorno.response and "resultado" not in retorno.response
    assert r["sqls_executados"][0]["erro"] and r["sqls_executados"][1]["erro"] is None


def test_ids_decimais_viram_inteiros_na_previsao():
    args = {"jogador_a_id": 206173.0, "jogador_b_id": 207989.0, "superficie": "Grass"}
    cliente = ClienteFalso(resposta(chamada("c1", "prever_partida", args)), resposta(texto("Sinner é favorito.")))
    r = AgenteGemini(client=cliente).perguntar("Sinner x Alcaraz na grama?")

    assert r["passos"][0]["erro"] is None
    assert r["passos"][0]["entrada"]["jogador_a_id"] == 206173


def test_grafico_vai_para_o_resultado():
    dados = [{"ano": 2023, "vitorias": 50}, {"ano": 2024, "vitorias": 60}]
    args = {"dados": dados, "tipo": "linha", "x": "ano", "y": "vitorias", "titulo": "Vitórias"}
    cliente = ClienteFalso(resposta(chamada("c1", "gerar_grafico", args)), resposta(texto("Pronto.")))
    r = AgenteGemini(client=cliente).perguntar("Gráfico de vitórias")

    assert len(r["graficos"]) == 1


def test_ultima_iteracao_desliga_as_tools():
    em_loop = [resposta(chamada(f"c{i}", "listar_tabelas", {})) for i in range(MAX_ITERACOES - 1)]
    cliente = ClienteFalso(*em_loop, resposta(texto("Resposta final.")))
    r = AgenteGemini(client=cliente).perguntar("Pergunta difícil")

    modos = [c["config"].tool_config.function_calling_config.mode for c in cliente.chamadas]
    assert modos[-1] == types.FunctionCallingConfigMode.NONE
    assert all(m == types.FunctionCallingConfigMode.AUTO for m in modos[:-1])
    assert r["resposta_texto"] == "Resposta final."


def test_parada_inesperada_nao_entra_no_historico():
    cliente = ClienteFalso(resposta(texto("Começo..."), motivo=types.FinishReason.MAX_TOKENS))
    r = AgenteGemini(client=cliente).perguntar("Conte tudo")

    assert "interrompida" in r["resposta_texto"]
    assert r["historico"] == []


def test_historico_continua_a_conversa():
    cliente = ClienteFalso(resposta(texto("Primeira.")), resposta(texto("Segunda.")))
    agente = AgenteGemini(client=cliente)
    r1 = agente.perguntar("Pergunta 1")
    agente.perguntar("Pergunta 2", r1["historico"])

    enviados = cliente.chamadas[1]["contents"]
    assert [c.role for c in enviados] == ["user", "model", "user"]


def _sobrecarga() -> errors.ServerError:
    return errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


def test_modelo_sobrecarregado_passa_para_a_reserva():
    cliente = ClienteFalso(httpx.ReadTimeout("tempo esgotado"), resposta(texto("Respondido pela reserva.")))
    r = AgenteGemini(modelo="principal", client=cliente).perguntar("Pergunta")

    assert r["resposta_texto"] == "Respondido pela reserva."
    assert [c["model"] for c in cliente.chamadas] == ["principal", MODELOS_RESERVA[0]]


def test_reserva_segue_ate_o_fim_da_pergunta():
    cliente = ClienteFalso(
        _sobrecarga(),
        resposta(chamada("c1", "listar_tabelas", {})),
        resposta(texto("Fim.")),
        resposta(texto("Nova pergunta.")),
    )
    agente = AgenteGemini(modelo="principal", client=cliente)
    r = agente.perguntar("Pergunta")
    agente.perguntar("Outra pergunta")

    reserva = MODELOS_RESERVA[0]
    assert [c["model"] for c in cliente.chamadas] == ["principal", reserva, reserva, "principal"]
    assert any(p["tipo"] == "aviso" and reserva in p["texto"] for p in r["passos"])


def test_todos_sobrecarregados_levanta_o_erro():
    cliente = ClienteFalso(*[_sobrecarga() for _ in range(len(MODELOS_RESERVA) + 1)])
    with pytest.raises(errors.ServerError):
        AgenteGemini(modelo="principal", client=cliente).perguntar("Pergunta")


def test_modelo_que_insiste_em_tools_recebe_aviso_e_nao_resposta_vazia():
    # Mesmo com as tools desligadas na última volta, o modelo continua chamando
    cliente = ClienteFalso(*[resposta(chamada(f"c{i}", "listar_tabelas", {})) for i in range(MAX_ITERACOES)])
    r = AgenteGemini(client=cliente).perguntar("Pergunta difícil")

    assert r["resposta_texto"].startswith("⚠️ Não consegui concluir")
    assert r["historico"] == []
