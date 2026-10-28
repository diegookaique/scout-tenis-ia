"""Funções que o agente pode chamar (tools) e suas definições para a Anthropic API."""

import threading
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import duckdb
import pandas as pd
import plotly.express as px

from src.db import cursor
from src.elo import RATING_INICIAL, combinar, prob_vitoria

LIMITE_LINHAS = 200
TIMEOUT_SEGUNDOS = 20
TIPOS_GRAFICO = ("barra", "linha", "dispersao", "radar")
# Cores bem distintas entre si e legíveis no tema claro e no escuro
CORES = ["#4C9BE8", "#F28E2B", "#59A14F", "#E15759", "#B07AA1", "#EDC948", "#76B7B2", "#FF9DA7"]


# ---------------------------------------------------------------- listar_tabelas


def listar_tabelas() -> str:
    """Retorna o esquema (tabelas, views, colunas e tipos) em texto."""
    linhas = cursor().execute("""
        SELECT c.table_name, t.table_type, c.column_name, c.data_type
        FROM information_schema.columns c
        JOIN information_schema.tables t USING (table_schema, table_name)
        WHERE c.table_schema = 'main'
        ORDER BY c.table_name, c.ordinal_position
    """).fetchall()
    esquema: dict[tuple[str, str], list[str]] = {}
    for tabela, tipo_tabela, coluna, tipo in linhas:
        esquema.setdefault((tabela, tipo_tabela), []).append(f"{coluna} {tipo}")
    blocos = []
    for (tabela, tipo_tabela), colunas in esquema.items():
        rotulo = "VIEW" if tipo_tabela == "VIEW" else "TABELA"
        blocos.append(f"{rotulo} {tabela}(\n  " + ",\n  ".join(colunas) + "\n)")
    return "\n\n".join(blocos)


# ---------------------------------------------------------------- buscar_jogador


def buscar_jogador(nome: str) -> list[dict[str, Any]]:
    """Busca aproximada por nome (sem acento, sem diferenciar maiúsculas), top 5.

    Compara a consulta com o nome completo e com cada palavra do nome, para
    aceitar só o sobrenome ou erros de digitação ("djokovich"). Empates são
    desempatados pelo número de partidas no circuito principal, para que
    "Fonseca" traga o João Fonseca antes de homônimos desconhecidos.
    """
    linhas = cursor().execute("""
        WITH alvo AS (SELECT lower(strip_accents(trim(?))) AS q),
        n AS (SELECT player_id, count(*) AS n_partidas FROM partidas_jogador GROUP BY ALL),
        candidatos AS (
            SELECT j.player_id, j.nome_completo, j.pais, j.data_nascimento,
                   coalesce(n.n_partidas, 0) AS n_partidas,
                   lower(strip_accents(j.nome_completo)) AS nome_norm
            FROM jogadores j LEFT JOIN n USING (player_id)
        )
        SELECT player_id, nome_completo, pais, data_nascimento, n_partidas,
               round(greatest(
                   jaro_winkler_similarity(nome_norm, q),
                   list_max(list_transform(
                       list_filter(string_split(nome_norm, ' '), lambda p: length(p) >= 3),
                       lambda p: jaro_winkler_similarity(p, q))),
                   CASE WHEN contains(nome_norm, q) THEN 0.97 ELSE 0 END
               ), 3) AS similaridade
        FROM candidatos, alvo
        WHERE similaridade >= 0.75
        ORDER BY similaridade DESC, n_partidas DESC
        LIMIT 5
    """, [nome]).fetchall()
    colunas = ["player_id", "nome", "pais", "data_nascimento", "n_partidas", "similaridade"]
    return [dict(zip(colunas, map(_valor_json, linha))) for linha in linhas]


# ---------------------------------------------------------------- consultar_sql


def validar_sql(sql: str) -> str | None:
    """Devolve uma mensagem de erro se o SQL não for uma única consulta de leitura."""
    try:
        comandos = duckdb.extract_statements(sql)
    except duckdb.Error as erro:
        return f"Erro de sintaxe: {erro}"
    if len(comandos) != 1:
        return "Envie exatamente um comando SQL por vez."
    if comandos[0].type != duckdb.StatementType.SELECT:
        return "Apenas consultas de leitura (SELECT ou WITH) são permitidas."
    return None


def consultar_sql(sql: str) -> dict[str, Any]:
    """Executa um SELECT/WITH e devolve {colunas, linhas, n_linhas, truncado, erro}.

    Devolve no máximo LIMITE_LINHAS linhas e interrompe consultas que passem de
    TIMEOUT_SEGUNDOS. Erros voltam como texto para o agente poder se corrigir.
    """
    resultado: dict[str, Any] = {"colunas": [], "linhas": [], "n_linhas": 0, "truncado": False, "erro": None}
    erro = validar_sql(sql)
    if erro:
        return resultado | {"erro": erro}

    cur = cursor()
    cronometro = threading.Timer(TIMEOUT_SEGUNDOS, cur.interrupt)
    cronometro.start()
    try:
        cur.execute(sql)
        linhas = cur.fetchmany(LIMITE_LINHAS + 1)
        colunas = [d[0] for d in cur.description]
    except duckdb.InterruptException:
        return resultado | {"erro": f"Consulta cancelada: passou de {TIMEOUT_SEGUNDOS} s. Simplifique ou filtre mais."}
    except duckdb.Error as erro:
        return resultado | {"erro": f"{type(erro).__name__}: {erro}"}
    finally:
        cronometro.cancel()

    truncado = len(linhas) > LIMITE_LINHAS
    linhas = [[_valor_json(v) for v in linha] for linha in linhas[:LIMITE_LINHAS]]
    return resultado | {"colunas": colunas, "linhas": linhas, "n_linhas": len(linhas), "truncado": truncado}


def _valor_json(valor: Any) -> Any:
    """Converte tipos do DuckDB para algo serializável em JSON."""
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


# ---------------------------------------------------------------- gerar_grafico


def gerar_grafico(
    dados: list[dict[str, Any]],
    tipo: str,
    x: str,
    y: str | list[str],
    titulo: str,
    serie: str | None = None,
) -> dict[str, Any]:
    """Monta um gráfico Plotly e devolve {figura (JSON), erro}.

    tipo: "barra" | "linha" | "dispersao" | "radar". No radar, x são as categorias
    (eixos) e y os valores. `serie` é a coluna que separa as cores (ex.: jogador).
    """
    erro = _validar_grafico(dados, tipo, x, y, serie)
    if erro:
        return {"figura": None, "erro": erro}
    # Nomes de coluna viram rótulos legíveis ("vitorias_sinner" → "Vitorias sinner")
    df = pd.DataFrame(dados).rename(columns=_rotulo)
    x, serie = _rotulo(x), _rotulo(serie) if serie else None
    y = _rotulo(y) if isinstance(y, str) else [_rotulo(c) for c in y]
    if tipo == "barra":
        fig = px.bar(df, x=x, y=y, color=serie, barmode="group", color_discrete_sequence=CORES)
    elif tipo == "linha":
        fig = px.line(df, x=x, y=y, color=serie, markers=True, color_discrete_sequence=CORES)
    elif tipo == "dispersao":
        fig = px.scatter(df, x=x, y=y, color=serie, color_discrete_sequence=CORES)
    else:
        fig = px.line_polar(df, theta=x, r=y, color=serie, line_close=True, color_discrete_sequence=CORES)
        fig.update_traces(fill="toself")
        # Fundo transparente para o radar acompanhar o tema claro ou escuro
        fig.update_layout(polar={"bgcolor": "rgba(0,0,0,0)"})
    # Sem template fixo: a interface aplica o tema dela (claro ou escuro)
    fig.update_layout(title=titulo, legend_title_text="")
    if not isinstance(y, str):  # várias séries: o eixo y genérico ("value") fica sem título
        fig.update_layout(yaxis_title="")
    return {"figura": fig.to_json(), "erro": None}


def _rotulo(coluna: str) -> str:
    texto = coluna.replace("_", " ")
    return texto[:1].upper() + texto[1:]


def _validar_grafico(
    dados: list[dict[str, Any]], tipo: str, x: str, y: str | list[str], serie: str | None
) -> str | None:
    if tipo not in TIPOS_GRAFICO:
        return f"Tipo inválido: {tipo}. Use um de {', '.join(TIPOS_GRAFICO)}."
    if not dados:
        return "Nenhum dado para o gráfico."
    if tipo == "radar" and not isinstance(y, str):
        return "No radar, y deve ser uma única coluna."
    colunas = [x, *([y] if isinstance(y, str) else y), *([serie] if serie else [])]
    faltando = [c for c in colunas if c not in dados[0]]
    if faltando:
        return f"Colunas inexistentes nos dados: {', '.join(faltando)}. Disponíveis: {', '.join(dados[0])}."
    return None


# ---------------------------------------------------------------- prever_partida

SUPERFICIES_PREVISAO = ("Hard", "Clay", "Grass")
MIN_PARTIDAS_CONFIAVEL = 20


def prever_partida(jogador_a_id: int, jogador_b_id: int, superficie: str) -> dict[str, Any]:
    """Probabilidade de A vencer B na superfície, pelo Elo combinado (geral + superfície).

    Usa o último rating de cada jogador (tabela elo_atual, gerada por
    scripts/calcular_elo.py). Devolve {jogador_a, jogador_b, prob_a, prob_b,
    favorito, avisos, erro}.
    """
    if superficie not in SUPERFICIES_PREVISAO:
        return {"erro": f"Superfície inválida: {superficie}. Use uma de {', '.join(SUPERFICIES_PREVISAO)}."}
    if jogador_a_id == jogador_b_id:
        return {"erro": "Escolha dois jogadores diferentes."}
    try:
        a, b = (_elo_do_jogador(int(j), superficie) for j in (jogador_a_id, jogador_b_id))
    except duckdb.CatalogException:
        return {"erro": "Tabela de Elo não encontrada. Rode: python scripts/calcular_elo.py"}
    faltando = [str(j) for j, dados in ((jogador_a_id, a), (jogador_b_id, b)) if dados is None]
    if faltando:
        return {"erro": f"Sem Elo para o(s) player_id {', '.join(faltando)}: confira com buscar_jogador."}

    prob_a = prob_vitoria(a["elo_combinado"], b["elo_combinado"])
    return {
        "superficie": superficie,
        "jogador_a": a,
        "jogador_b": b,
        "prob_a": round(prob_a, 3),
        "prob_b": round(1 - prob_a, 3),
        "favorito": a["nome"] if prob_a >= 0.5 else b["nome"],
        "avisos": _avisos_previsao(a, b),
        "erro": None,
    }


def _elo_do_jogador(player_id: int, superficie: str) -> dict[str, Any] | None:
    """Elo geral, da superfície e combinado de um jogador; None se ele não tem partidas."""
    linha = cursor().execute("""
        SELECT j.nome_completo,
               max(e.rating) FILTER (WHERE e.superficie = 'Geral') AS geral,
               max(e.rating) FILTER (WHERE e.superficie = $sup) AS sup,
               coalesce(max(e.partidas) FILTER (WHERE e.superficie = $sup), 0) AS partidas_sup,
               max(e.ultima_partida) AS ultima
        FROM jogadores j JOIN elo_atual e USING (player_id)
        WHERE player_id = $id
        GROUP BY j.nome_completo
    """, {"id": player_id, "sup": superficie}).fetchone()
    if linha is None:
        return None
    nome, geral, sup, partidas_sup, ultima = linha
    sup = sup if sup is not None else RATING_INICIAL  # nunca jogou na superfície
    return {
        "player_id": player_id,
        "nome": nome,
        "elo_geral": round(geral),
        "elo_superficie": round(sup),
        "elo_combinado": round(combinar(geral, sup)),
        "partidas_superficie": partidas_sup,
        "ultima_partida": _valor_json(ultima),
    }


def _avisos_previsao(*jogadores: dict[str, Any]) -> list[str]:
    avisos = [
        f"{j['nome']} tem só {j['partidas_superficie']} partida(s) nessa superfície: o Elo dela é pouco confiável."
        for j in jogadores
        if j["partidas_superficie"] < MIN_PARTIDAS_CONFIAVEL
    ]
    return avisos + [
        "O Elo vem só de resultados (não considera lesões, forma recente fora do circuito principal "
        "ou confronto direto). Acerta o vencedor em cerca de 64% das partidas desde 2023."
    ]


# ---------------------------------------------------------------- definições para a API

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "name": "listar_tabelas",
        "description": (
            "Mostra o esquema do banco de tênis: tabelas, views, colunas e tipos. "
            "Use quando tiver dúvida sobre nomes de colunas antes de escrever SQL."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "buscar_jogador",
        "description": (
            "Encontra o player_id de um jogador a partir do nome (aceita nome parcial, "
            "sem acento ou com erro de digitação). Retorna até 5 candidatos com país, "
            "data de nascimento, nº de partidas no circuito e similaridade. "
            "Sempre use antes de filtrar por jogador no SQL; filtre por player_id, nunca por nome."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome ou sobrenome do jogador, ex.: 'Joao Fonseca'."}
            },
            "required": ["nome"],
        },
    },
    {
        "name": "consultar_sql",
        "description": (
            "Executa UMA consulta SQL de leitura (SELECT ou WITH) no DuckDB e devolve "
            f"colunas e linhas (máximo {LIMITE_LINHAS}; 'truncado' indica se havia mais). "
            "Prefira agregar no SQL em vez de trazer muitas linhas. Se vier 'erro', "
            "leia a mensagem, corrija a consulta e tente de novo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "Consulta SQL no dialeto do DuckDB."}},
            "required": ["sql"],
        },
    },
    {
        "name": "gerar_grafico",
        "description": (
            "Gera um gráfico Plotly para mostrar ao usuário. Use para comparações "
            "(barra, radar), séries temporais (linha) ou relação entre duas medidas "
            "(dispersao). Passe em 'dados' as linhas já calculadas, como objetos {coluna: valor}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dados": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Linhas do gráfico, ex.: [{'ano': 2023, 'vitorias': 50}, ...].",
                },
                "tipo": {"type": "string", "enum": list(TIPOS_GRAFICO)},
                "x": {"type": "string", "description": "Coluna do eixo x (no radar: as categorias)."},
                "y": {
                    "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
                    "description": "Coluna(s) do eixo y (no radar: uma única coluna de valores).",
                },
                "titulo": {"type": "string", "description": "Título do gráfico, em português."},
                "serie": {
                    "type": "string",
                    "description": "Opcional: coluna que separa as séries por cor (ex.: 'jogador').",
                },
            },
            "required": ["dados", "tipo", "x", "y", "titulo"],
        },
    },
]

TOOLS_SCHEMA.append({
    "name": "prever_partida",
    "description": (
        "Estima a probabilidade de cada jogador vencer uma partida numa superfície, pelo rating Elo "
        "(média do Elo geral com o Elo da superfície, com os ratings mais recentes). Use quando o "
        "usuário perguntar quem venceria, quem é favorito ou qual a chance de vitória num confronto. "
        "Antes, obtenha os dois player_id com buscar_jogador. Retorna os ratings, prob_a, prob_b, o "
        "favorito e avisos (ex.: poucas partidas na superfície), que devem ser repassados ao usuário. "
        "Para o histórico de Elo, consulte as tabelas elo e elo_atual com consultar_sql."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "jogador_a_id": {"type": "integer", "description": "player_id do primeiro jogador."},
            "jogador_b_id": {"type": "integer", "description": "player_id do segundo jogador."},
            "superficie": {
                "type": "string",
                "enum": list(SUPERFICIES_PREVISAO),
                "description": "Hard = quadra dura, Clay = saibro, Grass = grama.",
            },
        },
        "required": ["jogador_a_id", "jogador_b_id", "superficie"],
    },
})

FUNCOES: dict[str, Any] = {
    "listar_tabelas": listar_tabelas,
    "buscar_jogador": buscar_jogador,
    "consultar_sql": consultar_sql,
    "gerar_grafico": gerar_grafico,
    "prever_partida": prever_partida,
}
