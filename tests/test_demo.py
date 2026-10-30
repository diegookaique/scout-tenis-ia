"""Testes do modo demonstração (usa o banco, não a API)."""

import json

import pytest

from src.db import CAMINHO_BANCO
from src.demo import GRUPOS_EXEMPLO, PERGUNTAS_EXEMPLO, AgenteDemo

pytestmark = pytest.mark.skipif(not CAMINHO_BANCO.exists(), reason="tenis.duckdb não encontrado")


@pytest.mark.parametrize("pergunta", PERGUNTAS_EXEMPLO)
def test_cada_exemplo_responde_sem_erro(pergunta):
    r = AgenteDemo().perguntar(pergunta)

    tools = [p for p in r["passos"] if p["tipo"] == "tool"]
    assert any(p["nome"] in ("consultar_sql", "prever_partida", "simular_torneio") for p in tools)
    assert not any(p["erro"] for p in tools)
    assert "Modo demonstração" in r["resposta_texto"]
    for figura in r["graficos"]:
        json.loads(figura)


def test_dez_perguntas_em_dois_grupos_de_cinco():
    assert len(PERGUNTAS_EXEMPLO) == 10
    assert [len(v) for v in GRUPOS_EXEMPLO.values()] == [5, 5]


def test_atp_finals_simula_os_8_primeiros():
    r = AgenteDemo().perguntar("Quem vai ganhar o ATP Finals de 2026?")
    simulacao = next(p for p in r["passos"] if p["nome"] == "simular_torneio")
    assert len(simulacao["entrada"]["jogadores_ids"]) == 8
    assert "**Jannik Sinner** é o favorito ao título" in r["resposta_texto"]
    assert "Avisos" in r["resposta_texto"] and len(r["graficos"]) == 1


def test_numero1_compara_metricas():
    r = AgenteDemo().perguntar("quem vai terminar 2026 como número 1?")
    assert "**Jannik Sinner**" in r["resposta_texto"]
    assert "13.500 pontos" in r["resposta_texto"] and "tendência" in r["resposta_texto"]


def test_previsao_elo_tem_favorito_e_grafico():
    r = AgenteDemo().perguntar("Sinner × Alcaraz no saibro: quem é favorito?")
    assert "é favorito" in r["resposta_texto"] and "Avisos" in r["resposta_texto"]
    assert len(r["graficos"]) == 1


def test_evolucao_elo_tres_jogadores():
    r = AgenteDemo().perguntar("Como evoluiu o Elo de Sinner, Alcaraz e Djokovic?")
    assert "Em 2026, **Jannik Sinner** tem o maior Elo" in r["resposta_texto"]
    figura = json.loads(r["graficos"][0])
    assert len(figura["data"]) == 3  # uma linha por jogador


def test_pergunta_livre_explica_o_modo_demo():
    r = AgenteDemo().perguntar("Quem é o maior sacador da história?")
    assert r["sqls_executados"] == []
    assert "GEMINI_API_KEY" in r["resposta_texto"]
