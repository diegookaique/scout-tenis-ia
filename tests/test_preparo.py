"""Testes da verificação do banco usada no deploy (não baixam nada)."""

import duckdb
import pytest

from src.db import CAMINHO_BANCO
from src.preparo import ULTIMA_TABELA, banco_pronto


def test_banco_ausente_nao_esta_pronto(tmp_path):
    assert not banco_pronto(tmp_path / "nao_existe.duckdb")


def test_banco_pela_metade_nao_esta_pronto(tmp_path):
    # Carga interrompida: o arquivo existe, mas sem a última tabela
    caminho = tmp_path / "parcial.duckdb"
    with duckdb.connect(str(caminho)) as con:
        con.execute("CREATE TABLE jogadores (player_id INTEGER)")
    assert not banco_pronto(caminho)


def test_banco_completo_esta_pronto(tmp_path):
    caminho = tmp_path / "completo.duckdb"
    with duckdb.connect(str(caminho)) as con:
        con.execute(f"CREATE TABLE {ULTIMA_TABELA} AS SELECT 1 AS x")
    assert banco_pronto(caminho)


@pytest.mark.skipif(not CAMINHO_BANCO.exists(), reason="tenis.duckdb não encontrado")
def test_banco_do_projeto_esta_pronto():
    assert banco_pronto()
