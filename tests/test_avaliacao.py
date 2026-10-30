"""Testes da correção automática da avaliação (não chamam a API)."""

import pytest

from src.avaliacao import Pergunta, carregar_perguntas, corrigir, numeros_no_texto, valores_esperados
from src.db import CAMINHO_BANCO


@pytest.mark.parametrize(("texto", "numero"), [
    ("Ele fez 1.260 aces", 1260),
    ("aproveitamento de 79,8%", 79.8),
    ("Elo de 2.282,1", 2282.1),
    ("1,260 aces in 2015", 1260),
    ("ganhou 22 Grand Slams.", 22),
    ("chance de 71.2%", 71.2),
])
def test_numeros_no_texto_formato_brasileiro_e_americano(texto, numero):
    assert numero in numeros_no_texto(texto)


def _pergunta(**campos) -> Pergunta:
    return Pergunta(id="x", categoria="teste", pergunta="?", **campos)


def test_valores_numero_e_nome():
    p = _pergunta()
    assert corrigir(p, "**Rafael Nadal** lidera, com 488 vitórias.", ["Nadal", 488])[0]
    acertou, motivo = corrigir(p, "Rafael Nadal lidera, com 480 vitórias.", ["Nadal", 488])
    assert not acertou and "488" in motivo


def test_nome_sem_acento_e_maiuscula():
    assert corrigir(_pergunta(), "JOÃO FONSECA venceu", ["Joao Fonseca"])[0]


def test_tolerancia_decimal():
    p = _pergunta(tolerancia=0.3)
    assert corrigir(p, "ganhou 79,9% dos pontos", [79.8])[0]
    assert not corrigir(p, "ganhou 80,7% dos pontos", [79.8])[0]  # média de percentuais: errado


def test_inteiro_exige_valor_exato():
    assert not corrigir(_pergunta(), "venceu 30 partidas", [31])[0]


def test_aceitar_alternativa_na_pergunta_ambigua():
    p = _pergunta(aceitar=["Mischa"])
    assert corrigir(p, "Você quer saber do Alexander ou do Mischa Zverev?", [57])[0]


def test_recusa():
    p = _pergunta(tipo="recusa", deve_conter=["2000"])
    assert corrigir(p, "Os dados começam em 2000, então não há registros de 1997.", [])[0]
    # resposta real do agente que o corretor recusava por engano
    assert corrigir(p, "Os dados cobrem o período a partir de 3 de janeiro de 2000, portanto não "
                       "registram as partidas e títulos de Gustavo Kuerten em 1997.", [])[0]
    assert not corrigir(p, "Não há dados desse ano.", [])[0]  # faltou citar 2000
    assert not corrigir(p, "Guga ganhou 3 títulos em 1997.", [])[0]  # inventou


@pytest.mark.skipif(not CAMINHO_BANCO.exists(), reason="tenis.duckdb não encontrado")
def test_toda_pergunta_tem_referencia_valida():
    perguntas = carregar_perguntas()
    assert 10 <= len(perguntas) <= 15
    assert len({p.id for p in perguntas}) == len(perguntas)
    for p in perguntas:
        esperados = valores_esperados(p)
        assert esperados or p.tipo == "recusa", p.id
