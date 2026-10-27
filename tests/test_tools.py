"""Testes das tools do agente. Requerem o banco: python scripts/carregar_dados.py"""

import json

import pytest

from src.db import CAMINHO_BANCO
from src.tools import (
    LIMITE_LINHAS,
    TOOLS_SCHEMA,
    buscar_jogador,
    consultar_sql,
    gerar_grafico,
    listar_tabelas,
    prever_partida,
)

pytestmark = pytest.mark.skipif(not CAMINHO_BANCO.exists(), reason="tenis.duckdb não encontrado")

ID_JOAO_FONSECA = 211663
ID_DJOKOVIC = 104925


# ---------------------------------------------------------------- listar_tabelas


def test_listar_tabelas_mostra_tabelas_e_view():
    esquema = listar_tabelas()
    for nome in ("TABELA jogadores", "TABELA partidas", "TABELA rankings", "VIEW partidas_jogador"):
        assert nome in esquema


# ---------------------------------------------------------------- buscar_jogador


@pytest.mark.parametrize("nome", ["joao fonseca", "João Fonseca", "JOAO FONSECA", "Fonseca"])
def test_buscar_jogador_joao_fonseca(nome):
    resultado = buscar_jogador(nome)
    assert resultado[0]["player_id"] == ID_JOAO_FONSECA
    assert resultado[0]["pais"] == "BRA"


def test_buscar_jogador_tolera_erro_de_digitacao():
    assert buscar_jogador("djokovich")[0]["player_id"] == ID_DJOKOVIC


def test_buscar_jogador_retorna_no_maximo_5():
    assert 1 <= len(buscar_jogador("silva")) <= 5


def test_buscar_jogador_sem_resultado():
    assert buscar_jogador("xqzwvk") == []


# ---------------------------------------------------------------- consultar_sql


def test_consultar_sql_select_valido():
    resultado = consultar_sql(
        f"SELECT count(*) AS vitorias FROM partidas_jogador WHERE player_id = {ID_DJOKOVIC} AND venceu"
    )
    assert resultado["erro"] is None
    assert resultado["colunas"] == ["vitorias"]
    assert resultado["linhas"][0][0] > 1000


def test_consultar_sql_aceita_with():
    resultado = consultar_sql("WITH t AS (SELECT 1 AS x) SELECT x FROM t")
    assert resultado["erro"] is None
    assert resultado["linhas"] == [[1]]


def test_consultar_sql_limita_linhas():
    resultado = consultar_sql("SELECT * FROM partidas")
    assert resultado["n_linhas"] == LIMITE_LINHAS
    assert resultado["truncado"] is True


def test_consultar_sql_datas_serializaveis():
    resultado = consultar_sql("SELECT min(tourney_date) AS inicio FROM partidas")
    json.dumps(resultado)
    assert resultado["linhas"][0][0] == "2000-01-03"


@pytest.mark.parametrize("sql", ["SELEC * FROM partidas", "SELECT coluna_que_nao_existe FROM partidas"])
def test_consultar_sql_invalido_devolve_erro(sql):
    resultado = consultar_sql(sql)
    assert resultado["erro"]
    assert resultado["linhas"] == []


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE partidas",
        "drop table partidas",
        "DELETE FROM jogadores",
        "INSERT INTO jogadores VALUES (1, 'x', 'R', NULL, 'BRA', 180)",
        "CREATE TABLE x AS SELECT 1",
        "COPY partidas TO 'vazamento.csv'",
        "ATTACH 'outro.duckdb'",
        "SELECT 1; DROP TABLE partidas",
    ],
)
def test_consultar_sql_bloqueia_escrita(sql):
    resultado = consultar_sql(sql)
    assert resultado["erro"]
    assert consultar_sql("SELECT count(*) FROM partidas")["linhas"][0][0] > 60000


def test_consultar_sql_bloqueia_leitura_de_arquivos():
    assert consultar_sql("SELECT * FROM read_csv('data/atp_players.csv')")["erro"]


# ---------------------------------------------------------------- gerar_grafico

DADOS = [
    {"superficie": "Hard", "pct_vitorias": 80.0, "jogador": "A"},
    {"superficie": "Clay", "pct_vitorias": 70.0, "jogador": "A"},
    {"superficie": "Grass", "pct_vitorias": 75.0, "jogador": "A"},
]


@pytest.mark.parametrize("tipo", ["barra", "linha", "dispersao", "radar"])
def test_gerar_grafico_tipos(tipo):
    resultado = gerar_grafico(DADOS, tipo, "superficie", "pct_vitorias", "Teste", serie="jogador")
    assert resultado["erro"] is None
    assert json.loads(resultado["figura"])["layout"]["title"]["text"] == "Teste"


@pytest.mark.parametrize(
    "tipo, x, y",
    [("pizza", "superficie", "pct_vitorias"), ("barra", "superficie", "coluna_errada")],
)
def test_gerar_grafico_parametros_invalidos(tipo, x, y):
    resultado = gerar_grafico(DADOS, tipo, x, y, "Teste")
    assert resultado["figura"] is None
    assert resultado["erro"]


# ---------------------------------------------------------------- prever_partida

ID_SINNER, ID_ALCARAZ = 206173, 207989


def test_prever_partida_probabilidades_somam_1():
    r = prever_partida(ID_SINNER, ID_ALCARAZ, "Clay")
    assert r["erro"] is None
    assert r["prob_a"] + r["prob_b"] == pytest.approx(1, abs=0.001)
    assert r["jogador_a"]["nome"] == "Jannik Sinner"
    assert r["favorito"] in ("Jannik Sinner", "Carlos Alcaraz")
    json.dumps(r)


def test_prever_partida_e_simetrica():
    ab = prever_partida(ID_SINNER, ID_ALCARAZ, "Hard")
    ba = prever_partida(ID_ALCARAZ, ID_SINNER, "Hard")
    assert ab["prob_a"] == pytest.approx(ba["prob_b"], abs=0.001)


def test_prever_partida_avisa_poucas_partidas():
    r = prever_partida(ID_JOAO_FONSECA, ID_DJOKOVIC, "Grass")
    assert any("Joao Fonseca" in aviso and "pouco confiável" in aviso for aviso in r["avisos"])


@pytest.mark.parametrize(
    "a, b, superficie",
    [(ID_SINNER, ID_ALCARAZ, "Carpet"), (ID_SINNER, ID_SINNER, "Clay"), (ID_SINNER, 999999999, "Clay")],
)
def test_prever_partida_entradas_invalidas(a, b, superficie):
    assert prever_partida(a, b, superficie)["erro"]


# ---------------------------------------------------------------- TOOLS_SCHEMA


def test_tools_schema_formato_anthropic():
    nomes = {tool["name"] for tool in TOOLS_SCHEMA}
    assert nomes == {"listar_tabelas", "buscar_jogador", "consultar_sql", "gerar_grafico", "prever_partida"}
    for tool in TOOLS_SCHEMA:
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"
