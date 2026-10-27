"""Calcula o Elo histórico por superfície e grava no tenis.duckdb.

Uso (depois de scripts/carregar_dados.py):
    python scripts/calcular_elo.py

Cria as tabelas:
    elo            histórico: rating de cada jogador após cada partida, por escala
    elo_atual      último rating de cada jogador em cada escala
    elo_validacao  acurácia das previsões feitas antes de cada partida (desde 2023)
"""

import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.elo import CalculadoraElo, Partida, metricas  # noqa: E402

CAMINHO_BANCO = RAIZ / "tenis.duckdb"
INICIO_VALIDACAO = date(2023, 1, 1)  # antes disso os ratings ainda estão "aquecendo"
# Escolhido pela validação: K fixo 32 teve Brier e log loss menores que o K dinâmico
K_ESCOLHIDO = 32.0

# Dentro de um torneio (mesma tourney_date), as rodadas seguem esta ordem
ORDEM_RODADAS = """CASE round
    WHEN 'ER' THEN 0 WHEN 'RR' THEN 1 WHEN 'R128' THEN 2 WHEN 'R64' THEN 3
    WHEN 'R32' THEN 4 WHEN 'R16' THEN 5 WHEN 'QF' THEN 6 WHEN 'SF' THEN 7
    WHEN 'BR' THEN 8 WHEN 'F' THEN 9 ELSE 5 END"""


def ler_partidas(con: duckdb.DuckDBPyConnection) -> list[Partida]:
    """Partidas válidas em ordem cronológica (sem W/O, que não foram jogadas)."""
    linhas = con.execute(f"""
        SELECT tourney_date, winner_id, loser_id, surface
        FROM partidas
        WHERE surface IS NOT NULL AND coalesce(score, '') NOT ILIKE '%W/O%'
        ORDER BY tourney_date, tourney_id, {ORDEM_RODADAS}, match_num
    """).fetchall()
    return [Partida(d, int(v), int(p), s) for d, v, p, s in linhas]


def acuracia_ranking(con: duckdb.DuckDBPyConnection) -> dict[str, float]:
    """Referência: o mais bem ranqueado na ATP vence (só partidas com os dois rankings)."""
    n, acertos = con.execute("""
        SELECT count(*), count(*) FILTER (WHERE winner_rank < loser_rank)
        FROM partidas
        WHERE tourney_date >= ? AND winner_rank IS NOT NULL AND loser_rank IS NOT NULL
          AND coalesce(score, '') NOT ILIKE '%W/O%'
    """, [INICIO_VALIDACAO]).fetchone()
    return {"fator_k": "-", "metodo": "ranking ATP (referência)", "partidas": n,
            "acuracia": acertos / n, "brier": None, "log_loss": None}


def validar(partidas: list[Partida], con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Compara K fixo (32) e K dinâmico, e Elo da superfície, geral e combinado."""
    resultados = [acuracia_ranking(con)]
    for nome_k, k_fixo in (("K dinâmico", None), ("K = 32", 32.0)):
        previsoes = [prev for prev, _ in CalculadoraElo(k_fixo).processar(partidas)
                     if prev.data >= INICIO_VALIDACAO]
        for metodo, campo in (("superfície", "prob_superficie"), ("geral", "prob_geral"),
                              ("combinado", "prob_combinada")):
            m = metricas([getattr(p, campo) for p in previsoes])
            resultados.append({"fator_k": nome_k, "metodo": metodo, **m})
    return pd.DataFrame(resultados)


def gravar(con: duckdb.DuckDBPyConnection, partidas: list[Partida]) -> int:
    """Roda o modelo escolhido (K_ESCOLHIDO) e grava histórico e ratings atuais."""
    historico = [
        (a.player_id, a.escala, a.data, round(a.rating, 1), a.partidas)
        for _, atualizacoes in CalculadoraElo(K_ESCOLHIDO).processar(partidas)
        for a in atualizacoes
    ]
    df = pd.DataFrame(historico, columns=["player_id", "superficie", "data", "rating", "partidas"])
    con.execute("DROP TABLE IF EXISTS elo")
    con.execute("CREATE TABLE elo AS SELECT player_id::INTEGER AS player_id, superficie, "
                "data::DATE AS data, rating, partidas::INTEGER AS partidas FROM df")
    con.execute("DROP TABLE IF EXISTS elo_atual")
    con.execute("""
        CREATE TABLE elo_atual AS
        SELECT player_id, superficie, arg_max(rating, data) AS rating,
               max(partidas) AS partidas, max(data) AS ultima_partida
        FROM elo GROUP BY player_id, superficie
    """)
    return len(df)


def main() -> None:
    if not CAMINHO_BANCO.exists():
        sys.exit("Banco não encontrado. Rode antes: python scripts/carregar_dados.py")
    with duckdb.connect(str(CAMINHO_BANCO)) as con:
        partidas = ler_partidas(con)
        print(f"Calculando Elo em {len(partidas):,} partidas...")
        n_linhas = gravar(con, partidas)

        validacao = validar(partidas, con)
        con.execute("DROP TABLE IF EXISTS elo_validacao")
        con.execute("CREATE TABLE elo_validacao AS SELECT * FROM validacao")

        print(f"  tabela elo: {n_linhas:,} linhas; elo_atual e elo_validacao criadas")
        print(f"\nValidação (previsões antes de cada partida, desde {INICIO_VALIDACAO:%d/%m/%Y}):")
        print(validacao.to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
