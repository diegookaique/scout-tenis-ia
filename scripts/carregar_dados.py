"""Baixa os CSVs da ATP (Jeff Sackmann) e monta o banco tenis.duckdb.

Uso:
    python scripts/carregar_dados.py            # baixa só o que falta
    python scripts/carregar_dados.py --forcar   # rebaixa tudo
"""

import argparse
import os
from datetime import date
from pathlib import Path

import duckdb
import requests

# O repositório original (JeffSackmann/tennis_atp) saiu do GitHub; usamos um fork com
# os mesmos commits do autor. Pode ser trocado pela variável de ambiente TENNIS_ATP_URL.
URL_BASE = os.getenv(
    "TENNIS_ATP_URL", "https://raw.githubusercontent.com/Kadantte/tennis_atp/master/"
)
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
CAMINHO_BANCO = RAIZ / "tenis.duckdb"
ANO_INICIAL = 2000
ARQUIVOS_RANKING = ["atp_rankings_10s.csv", "atp_rankings_20s.csv", "atp_rankings_current.csv"]


def baixar_arquivo(nome: str, forcar: bool) -> bool:
    """Baixa um CSV para data/. Retorna False se o arquivo não existe no repositório (404)."""
    destino = PASTA_DADOS / nome
    if destino.exists() and not forcar:
        return True
    resposta = requests.get(URL_BASE + nome, timeout=60)
    if resposta.status_code == 404:
        return False
    resposta.raise_for_status()
    destino.write_bytes(resposta.content)
    print(f"  baixado: {nome} ({len(resposta.content) / 1024:.0f} KB)")
    return True


def baixar_tudo(forcar: bool) -> list[Path]:
    """Baixa partidas, jogadores e rankings. Retorna os CSVs de partidas disponíveis."""
    PASTA_DADOS.mkdir(exist_ok=True)
    print("Baixando arquivos...")
    arquivos_partidas = []
    for ano in range(ANO_INICIAL, date.today().year + 1):
        nome = f"atp_matches_{ano}.csv"
        if baixar_arquivo(nome, forcar):
            arquivos_partidas.append(PASTA_DADOS / nome)
        else:
            print(f"  aviso: {nome} ainda não existe no repositório (ignorado)")
    for nome in ["atp_players.csv", *ARQUIVOS_RANKING]:
        if not baixar_arquivo(nome, forcar):
            raise RuntimeError(f"Arquivo obrigatório não encontrado: {nome}")
    return arquivos_partidas


def caminho_sql(caminho: Path) -> str:
    """Formata um caminho para uso dentro de SQL (barras normais, aspas simples)."""
    return "'" + caminho.as_posix().replace("'", "''") + "'"


def criar_jogadores(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"""
        CREATE TABLE jogadores AS
        SELECT
            player_id::INTEGER AS player_id,
            trim(concat_ws(' ', name_first, name_last)) AS nome_completo,
            hand AS mao,
            try_strptime(CAST(dob AS VARCHAR), '%Y%m%d')::DATE AS data_nascimento,
            ioc AS pais,
            TRY_CAST(height AS INTEGER) AS altura_cm
        FROM read_csv({caminho_sql(PASTA_DADOS / 'atp_players.csv')},
                      header = true, all_varchar = true)
    """)


def criar_partidas(con: duckdb.DuckDBPyConnection, arquivos: list[Path]) -> None:
    lista = "[" + ", ".join(caminho_sql(a) for a in arquivos) + "]"
    # union_by_name lida com colunas que variam entre anos; seeds podem ter texto ("Q", "WC")
    con.execute(f"""
        CREATE TABLE partidas AS
        SELECT
            * REPLACE (strptime(CAST(tourney_date AS VARCHAR), '%Y%m%d')::DATE AS tourney_date),
            year(strptime(CAST(tourney_date AS VARCHAR), '%Y%m%d')) AS ano
        FROM read_csv({lista}, union_by_name = true, sample_size = -1,
                      types = {{'winner_seed': 'VARCHAR', 'loser_seed': 'VARCHAR',
                               'tourney_date': 'VARCHAR'}})
    """)


def criar_rankings(con: duckdb.DuckDBPyConnection) -> None:
    lista = "[" + ", ".join(caminho_sql(PASTA_DADOS / n) for n in ARQUIVOS_RANKING) + "]"
    con.execute(f"""
        CREATE TABLE rankings AS
        SELECT DISTINCT
            strptime(CAST(ranking_date AS VARCHAR), '%Y%m%d')::DATE AS data_ranking,
            rank::INTEGER AS posicao,
            player::INTEGER AS player_id,
            TRY_CAST(points AS INTEGER) AS pontos
        FROM read_csv({lista}, header = true, all_varchar = true)
    """)


def colunas_perspectiva(eu: str, outro: str, venceu: bool) -> str:
    """Colunas da view partidas_jogador vistas pelo jogador `eu` ('winner'/'loser')."""
    p, a = eu[0], outro[0]  # prefixos das estatísticas: w_ / l_
    return f"""
            {eu}_id AS player_id, {eu}_name AS nome,
            {outro}_id AS adversario_id, {outro}_name AS adversario_nome,
            {str(venceu).upper()} AS venceu,
            surface AS superficie, tourney_date AS data, ano,
            tourney_id AS torneio_id, tourney_name AS torneio, tourney_level AS nivel_torneio,
            round AS rodada, best_of AS melhor_de, score AS placar, minutes AS minutos,
            {eu}_rank AS ranking, {outro}_rank AS adversario_ranking,
            {p}_ace AS aces, {p}_df AS duplas_faltas,
            {p}_svpt AS pontos_saque, {p}_1stIn AS primeiro_saque_dentro,
            {p}_1stWon AS pontos_ganhos_1o_saque, {p}_2ndWon AS pontos_ganhos_2o_saque,
            {p}_SvGms AS games_saque,
            round(100.0 * {p}_1stIn / nullif({p}_svpt, 0), 1) AS pct_primeiro_saque,
            round(100.0 * {p}_1stWon / nullif({p}_1stIn, 0), 1) AS pct_pontos_1o_saque,
            round(100.0 * {p}_2ndWon / nullif({p}_svpt - {p}_1stIn, 0), 1) AS pct_pontos_2o_saque,
            {p}_bpSaved AS bp_salvos, {p}_bpFaced AS bp_enfrentados,
            {a}_ace AS adversario_aces, {a}_bpSaved AS adversario_bp_salvos,
            {a}_bpFaced AS adversario_bp_enfrentados"""


def criar_view_partidas_jogador(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"""
        CREATE VIEW partidas_jogador AS
        SELECT {colunas_perspectiva('winner', 'loser', True)} FROM partidas
        UNION ALL
        SELECT {colunas_perspectiva('loser', 'winner', False)} FROM partidas
    """)


def imprimir_resumo(con: duckdb.DuckDBPyConnection) -> None:
    n_partidas, inicio, fim = con.execute(
        "SELECT count(*), min(tourney_date), max(tourney_date) FROM partidas"
    ).fetchone()
    n_jogadores = con.execute("SELECT count(*) FROM jogadores").fetchone()[0]
    n_rankings, rank_ini, rank_fim = con.execute(
        "SELECT count(*), min(data_ranking), max(data_ranking) FROM rankings"
    ).fetchone()
    print("\nResumo do banco:")
    print(f"  partidas:  {n_partidas:,} ({inicio} a {fim})")
    print(f"  jogadores: {n_jogadores:,}")
    print(f"  rankings:  {n_rankings:,} linhas ({rank_ini} a {rank_fim})")


def montar_banco(arquivos_partidas: list[Path]) -> None:
    """Recria o tenis.duckdb do zero a partir dos CSVs."""
    CAMINHO_BANCO.unlink(missing_ok=True)
    print(f"\nMontando {CAMINHO_BANCO.name}...")
    with duckdb.connect(str(CAMINHO_BANCO)) as con:
        criar_jogadores(con)
        criar_partidas(con, arquivos_partidas)
        criar_rankings(con)
        criar_view_partidas_jogador(con)
        imprimir_resumo(con)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forcar", action="store_true", help="rebaixa os CSVs mesmo se já existirem")
    args = parser.parse_args()
    montar_banco(baixar_tudo(args.forcar))


if __name__ == "__main__":
    main()
