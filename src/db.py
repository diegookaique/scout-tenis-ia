"""Conexão somente leitura com o banco tenis.duckdb."""

from functools import lru_cache
from pathlib import Path

import duckdb

CAMINHO_BANCO = Path(__file__).resolve().parent.parent / "tenis.duckdb"


@lru_cache(maxsize=1)
def conectar() -> duckdb.DuckDBPyConnection:
    """Abre (uma única vez) a conexão read-only, sem acesso a arquivos externos ou rede."""
    if not CAMINHO_BANCO.exists():
        raise FileNotFoundError(
            f"Banco não encontrado em {CAMINHO_BANCO}. Rode: python scripts/carregar_dados.py"
        )
    return duckdb.connect(
        str(CAMINHO_BANCO), read_only=True, config={"enable_external_access": False}
    )


def cursor() -> duckdb.DuckDBPyConnection:
    """Cursor novo sobre a conexão compartilhada (seguro para usar em outra thread)."""
    return conectar().cursor()
