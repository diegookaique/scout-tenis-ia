"""Monta o banco na primeira execução (ex.: no Streamlit Community Cloud).

O tenis.duckdb não vai para o GitHub. No servidor, ele é montado a partir dos CSVs
públicos na primeira vez que o app abre (cerca de 1 a 2 minutos) e reaproveitado
nas visitas seguintes.
"""

import sys
from pathlib import Path

import duckdb

from src.db import CAMINHO_BANCO, CONFIG_LEITURA

PASTA_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
# Última tabela criada pela carga (scripts/calcular_elo.py): se ela existe, o banco está completo
ULTIMA_TABELA = "elo_validacao"


def banco_pronto(caminho: Path = CAMINHO_BANCO) -> bool:
    """True se o banco existe e a carga terminou (um banco pela metade conta como ausente)."""
    if not caminho.exists():
        return False
    try:
        with duckdb.connect(str(caminho), read_only=True, config=CONFIG_LEITURA) as con:
            con.execute(f"SELECT 1 FROM {ULTIMA_TABELA} LIMIT 1")
        return True
    except duckdb.Error:
        return False


def preparar_banco() -> None:
    """Baixa os CSVs, monta o tenis.duckdb do zero e calcula o Elo (o mesmo que carregar_dados.py)."""
    if str(PASTA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(PASTA_SCRIPTS))
    from calcular_elo import main as calcular_elo
    from carregar_dados import baixar_tudo, montar_banco

    montar_banco(baixar_tudo(forcar=False))
    calcular_elo()
