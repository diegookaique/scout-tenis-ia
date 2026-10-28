"""Testes do modo demonstração (usa o banco, não a API)."""

import json

import pytest

from src.db import CAMINHO_BANCO
from src.demo import PERGUNTAS_EXEMPLO, AgenteDemo

pytestmark = pytest.mark.skipif(not CAMINHO_BANCO.exists(), reason="tenis.duckdb não encontrado")


@pytest.mark.parametrize("pergunta", PERGUNTAS_EXEMPLO)
def test_cada_exemplo_responde_sem_erro(pergunta):
    r = AgenteDemo().perguntar(pergunta)

    tools = [p for p in r["passos"] if p["tipo"] == "tool"]
    assert any(p["nome"] in ("consultar_sql", "prever_partida") for p in tools)
    assert not any(p["erro"] for p in tools)
    assert "Modo demonstração" in r["resposta_texto"]
    for figura in r["graficos"]:
        json.loads(figura)


def test_grand_slams_lider_e_djokovic():
    r = AgenteDemo().perguntar("Quem mais venceu Grand Slams desde 2000?")
    assert "**Novak Djokovic**" in r["resposta_texto"]


def test_aces_isner_2015():
    r = AgenteDemo().perguntar("quantos aces o isner fez em 2015?")
    assert "1.260 aces" in r["resposta_texto"]


def test_previsao_elo_tem_favorito_e_grafico():
    r = AgenteDemo().perguntar("Sinner × Alcaraz na grama: quem é favorito?")
    assert "é favorito" in r["resposta_texto"] and "Avisos" in r["resposta_texto"]
    assert len(r["graficos"]) == 1


def test_evolucao_elo_big3():
    r = AgenteDemo().perguntar("Como evoluiu o Elo do Big 3 ao longo dos anos?")
    assert "**Novak Djokovic em 2015**" in r["resposta_texto"]
    figura = json.loads(r["graficos"][0])
    assert len(figura["data"]) == 3  # uma linha por jogador


def test_pergunta_livre_explica_o_modo_demo():
    r = AgenteDemo().perguntar("Quem é o maior sacador da história?")
    assert r["sqls_executados"] == []
    assert "ANTHROPIC_API_KEY" in r["resposta_texto"]
