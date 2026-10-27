"""Testes da matemática do Elo (não precisam do banco)."""

from datetime import date

import pytest

from src.elo import GERAL, RATING_INICIAL, CalculadoraElo, Partida, fator_k, metricas, prob_vitoria


def test_ratings_iguais_dao_50_por_cento():
    assert prob_vitoria(1500, 1500) == 0.5


def test_400_pontos_de_diferenca_dao_10_para_1():
    assert prob_vitoria(1900, 1500) == pytest.approx(10 / 11)
    assert prob_vitoria(1500, 1900) == pytest.approx(1 / 11)


def test_fator_k_fixo_e_dinamico():
    assert fator_k(0, k_fixo=32) == 32
    assert fator_k(0) > fator_k(100) > fator_k(1000)


def test_primeira_partida_move_16_pontos_com_k_32():
    calc = CalculadoraElo(k_fixo=32)
    previsao, atualizacoes = next(calc.processar([Partida(date(2024, 1, 1), 1, 2, "Clay")]))

    assert previsao.prob_combinada == 0.5
    assert calc.rating[(1, GERAL)] == RATING_INICIAL + 16
    assert calc.rating[(2, "Clay")] == RATING_INICIAL - 16
    assert calc.rating[(1, "Hard")] == RATING_INICIAL  # outra superfície não muda
    # vencedor e perdedor, no Elo geral e no da superfície
    assert {(a.player_id, a.escala) for a in atualizacoes} == {(1, GERAL), (2, GERAL), (1, "Clay"), (2, "Clay")}


def test_soma_dos_ratings_se_conserva_com_k_fixo():
    partidas = [Partida(date(2024, 1, d), 1 + d % 3, 1 + (d + 1) % 3, "Hard") for d in range(1, 20)]
    calc = CalculadoraElo(k_fixo=32)
    list(calc.processar(partidas))
    total = sum(calc.rating[(j, GERAL)] for j in (1, 2, 3))
    assert total == pytest.approx(3 * RATING_INICIAL)


def test_previsao_usa_so_partidas_anteriores():
    partidas = [Partida(date(2024, 1, d), 1, 2, "Grass") for d in range(1, 6)]
    previsoes = [prev.prob_combinada for prev, _ in CalculadoraElo(k_fixo=32).processar(partidas)]
    assert previsoes[0] == 0.5
    assert previsoes == sorted(previsoes)  # o favorito fica mais favorito a cada vitória


def test_metricas():
    m = metricas([0.8, 0.6, 0.4, 0.5])
    assert m["partidas"] == 4
    assert m["acuracia"] == pytest.approx(2.5 / 4)  # 0.5 conta meio acerto
    assert m["brier"] == pytest.approx((0.04 + 0.16 + 0.36 + 0.25) / 4)
