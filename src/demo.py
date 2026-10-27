"""Modo demonstração: responde as perguntas de exemplo sem chamar a Claude API.

Cada exemplo segue o mesmo caminho do agente (buscar_jogador → consultar_sql →
gerar_grafico) com consultas prontas, e devolve o mesmo formato de resultado de
AgenteTenis.perguntar. Serve para usar a interface sem chave da API.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.tools import buscar_jogador, consultar_sql, gerar_grafico, prever_partida

AVISO = "_Modo demonstração: resposta de uma consulta pronta, sem IA._"
FONTE = "Fonte: dados de Jeff Sackmann (tennis_atp)."


@dataclass
class Exemplo:
    """Uma pergunta de exemplo com a consulta e o gráfico que a respondem."""

    pergunta: str
    jogadores: list[str]
    sql: str
    resumir: Callable[[list[dict[str, Any]]], str]
    grafico: dict[str, Any] | None = None
    # Exemplos de previsão chamam prever_partida(a, b, superfície) em vez de SQL
    previsao: tuple[int, int, str] | None = None


def _num(valor: float, casas: int = 0) -> str:
    """Formata no padrão brasileiro: 1.260 e 79,5."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- resumos


def _resumo_h2h(linhas: list[dict[str, Any]]) -> str:
    sinner = sum(l["vitorias_sinner"] for l in linhas)
    alcaraz = sum(l["vitorias_alcaraz"] for l in linhas)
    lider = "Alcaraz" if alcaraz > sinner else "Sinner"
    por_sup = "; ".join(f"{l['superficie']}: {l['vitorias_sinner']}–{l['vitorias_alcaraz']}" for l in linhas)
    return (f"**Sinner {sinner} × {alcaraz} Alcaraz** no circuito principal, com vantagem de {lider}.\n\n"
            f"Por superfície (Sinner–Alcaraz): {por_sup}.")


def _resumo_slams(linhas: list[dict[str, Any]]) -> str:
    top = linhas[0]
    resto = ", ".join(f"{l['jogador']} ({l['titulos']})" for l in linhas[1:5])
    return (f"**{top['jogador']}**, com **{top['titulos']} títulos de Grand Slam** desde 2000.\n\n"
            f"Na sequência: {resto}.")


def _resumo_isner(linhas: list[dict[str, Any]]) -> str:
    l = linhas[0]
    return (f"**{_num(l['aces'])} aces** em {l['partidas']} partidas do circuito principal em 2015, "
            f"média de {_num(l['aces'] / l['com_estatistica'], 1)} por partida.\n\n"
            f"{l['partidas'] - l['com_estatistica']} partida(s) não têm estatística de saque e ficaram fora da soma.")


def _resumo_djokovic(linhas: list[dict[str, Any]]) -> str:
    melhor = max(linhas, key=lambda l: l["pct_vitorias"])
    return (f"O melhor ano foi **{melhor['ano']}**, com **{_num(melhor['pct_vitorias'], 1)}%** de vitórias "
            f"({melhor['vitorias']} em {melhor['partidas']} partidas).\n\n"
            f"O gráfico mostra a série de {linhas[0]['ano']} a {linhas[-1]['ano']} "
            "(só anos com pelo menos 10 partidas).")


def _resumo_aces(linhas: list[dict[str, Any]]) -> str:
    top = linhas[0]
    return (f"**{top['jogador']}**, com **{_num(top['aces'])} aces** em 2023.\n\n"
            "O gráfico mostra o top 10. A soma só conta partidas com estatística de saque.")


def _resumo_fonseca(linhas: list[dict[str, Any]]) -> str:
    total = sum(l["partidas"] for l in linhas)
    vitorias = sum(l["vitorias"] for l in linhas)
    por_sup = "; ".join(f"{l['superficie']}: {l['vitorias']}/{l['partidas']} ({_num(l['pct_vitorias'], 1)}%)"
                        for l in linhas)
    return (f"**{vitorias} vitórias em {total} partidas** ({_num(100 * vitorias / total, 1)}%) no circuito principal.\n\n"
            f"Por superfície: {por_sup}.")


def _resumo_elo_saibro(linhas: list[dict[str, Any]]) -> str:
    top = linhas[0]
    resto = ", ".join(f"{l['jogador']} ({_num(l['elo'])})" for l in linhas[1:5])
    return (f"**{top['jogador']}**, com **Elo {_num(top['elo'])}** no saibro.\n\n"
            f"Na sequência: {resto}. Só entram jogadores com partida em 2026.")


def _resumo_previsao(linhas: list[dict[str, Any]]) -> str:
    p = linhas[0]
    a, b = p["jogador_a"], p["jogador_b"]
    favorito = a if p["prob_a"] >= 0.5 else b
    chance = max(p["prob_a"], p["prob_b"])
    superficie = {"Hard": "quadra dura", "Clay": "saibro", "Grass": "grama"}[p["superficie"]]
    detalhes = "\n".join(
        f"- {j['nome']}: Elo geral {_num(j['elo_geral'])}, Elo {superficie} {_num(j['elo_superficie'])} "
        f"({j['partidas_superficie']} partidas), combinado {_num(j['elo_combinado'])}"
        for j in (a, b)
    )
    avisos = "\n".join(f"- {aviso}" for aviso in p["avisos"])
    return (f"Pelo Elo, **{favorito['nome']}** é favorito, com **{_num(100 * chance, 1)}%** de chance.\n\n"
            f"{detalhes}\n\n**Avisos:**\n{avisos}")


# ---------------------------------------------------------------- exemplos

EXEMPLOS: list[Exemplo] = [
    Exemplo(
        pergunta="Qual o H2H entre Sinner e Alcaraz por superfície?",
        jogadores=["Sinner", "Alcaraz"],
        sql="""SELECT superficie,
       count(*) FILTER (WHERE venceu) AS vitorias_sinner,
       count(*) FILTER (WHERE NOT venceu) AS vitorias_alcaraz
FROM partidas_jogador
WHERE player_id = 206173 AND adversario_id = 207989
GROUP BY superficie ORDER BY superficie""",
        resumir=_resumo_h2h,
        grafico={"tipo": "barra", "x": "superficie", "y": ["vitorias_sinner", "vitorias_alcaraz"],
                 "titulo": "Sinner × Alcaraz por superfície"},
    ),
    Exemplo(
        pergunta="Quem mais venceu Grand Slams desde 2000?",
        jogadores=[],
        sql="""SELECT any_value(nome) AS jogador, count(*) AS titulos
FROM partidas_jogador
WHERE nivel_torneio = 'G' AND rodada = 'F' AND venceu
GROUP BY player_id ORDER BY titulos DESC LIMIT 10""",
        resumir=_resumo_slams,
        grafico={"tipo": "barra", "x": "jogador", "y": "titulos", "titulo": "Títulos de Grand Slam desde 2000"},
    ),
    Exemplo(
        pergunta="Quantos aces o Isner fez em 2015?",
        jogadores=["Isner"],
        sql="""SELECT sum(aces) AS aces, count(*) AS partidas, count(aces) AS com_estatistica
FROM partidas_jogador
WHERE player_id = 104545 AND ano = 2015""",
        resumir=_resumo_isner,
    ),
    Exemplo(
        pergunta="Como evoluiu o % de vitórias do Djokovic por ano?",
        jogadores=["Djokovic"],
        sql="""SELECT ano, count(*) AS partidas,
       count(*) FILTER (WHERE venceu) AS vitorias,
       round(100.0 * count(*) FILTER (WHERE venceu) / count(*), 1) AS pct_vitorias
FROM partidas_jogador
WHERE player_id = 104925
GROUP BY ano HAVING count(*) >= 10 ORDER BY ano""",
        resumir=_resumo_djokovic,
        grafico={"tipo": "linha", "x": "ano", "y": "pct_vitorias", "titulo": "Djokovic: % de vitórias por ano"},
    ),
    Exemplo(
        pergunta="Quem fez mais aces em 2023?",
        jogadores=[],
        sql="""SELECT any_value(nome) AS jogador, sum(aces) AS aces
FROM partidas_jogador
WHERE ano = 2023
GROUP BY player_id ORDER BY aces DESC NULLS LAST LIMIT 10""",
        resumir=_resumo_aces,
        grafico={"tipo": "barra", "x": "jogador", "y": "aces", "titulo": "Top 10 em aces, 2023"},
    ),
    Exemplo(
        pergunta="Qual o retrospecto do João Fonseca por superfície?",
        jogadores=["João Fonseca"],
        sql="""SELECT superficie, count(*) AS partidas,
       count(*) FILTER (WHERE venceu) AS vitorias,
       round(100.0 * count(*) FILTER (WHERE venceu) / count(*), 1) AS pct_vitorias
FROM partidas_jogador
WHERE player_id = 211663
GROUP BY superficie ORDER BY superficie""",
        resumir=_resumo_fonseca,
        grafico={"tipo": "radar", "x": "superficie", "y": "pct_vitorias",
                 "titulo": "João Fonseca: % de vitórias por superfície"},
    ),
    Exemplo(
        pergunta="Quem tem o maior Elo no saibro hoje?",
        jogadores=[],
        sql="""SELECT j.nome_completo AS jogador, round(e.rating) AS elo, e.partidas
FROM elo_atual e JOIN jogadores j USING (player_id)
WHERE e.superficie = 'Clay' AND e.ultima_partida >= DATE '2026-01-01'
ORDER BY e.rating DESC LIMIT 10""",
        resumir=_resumo_elo_saibro,
        grafico={"tipo": "barra", "x": "jogador", "y": "elo", "titulo": "Top 10 Elo no saibro (ativos em 2026)"},
    ),
    Exemplo(
        pergunta="Quem é favorito em Sinner × Alcaraz na grama, pelo Elo?",
        jogadores=["Sinner", "Alcaraz"],
        sql="",
        resumir=_resumo_previsao,
        previsao=(206173, 207989, "Grass"),
    ),
]

PERGUNTAS_EXEMPLO = [e.pergunta for e in EXEMPLOS]


class AgenteDemo:
    """Mesma interface de AgenteTenis, mas só responde as perguntas de exemplo."""

    modelo = "demonstração (sem IA)"

    def perguntar(self, pergunta: str, historico: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        resultado: dict[str, Any] = {
            "resposta_texto": "", "sqls_executados": [], "graficos": [], "n_iteracoes": 0,
            "passos": [], "uso": {"entrada": 0, "saida": 0, "cache_lido": 0, "cache_gravado": 0},
            "historico": historico or [],
        }
        exemplo = _encontrar(pergunta)
        if exemplo is None:
            resultado["resposta_texto"] = (
                "No modo demonstração eu só respondo as perguntas de exemplo da barra lateral. "
                "Para perguntas livres, o app precisa de uma chave da Claude API "
                "(variável ANTHROPIC_API_KEY)."
            )
            return resultado
        return _responder(exemplo, resultado)


def _encontrar(pergunta: str) -> Exemplo | None:
    alvo = pergunta.strip().lower()
    return next((e for e in EXEMPLOS if e.pergunta.lower() == alvo), None)


def _responder(exemplo: Exemplo, resultado: dict[str, Any]) -> dict[str, Any]:
    for nome in exemplo.jogadores:
        achado = buscar_jogador(nome)[:1]
        resultado["passos"].append({"tipo": "tool", "nome": "buscar_jogador", "entrada": {"nome": nome},
                                    "erro": None, "saida": achado})

    if exemplo.previsao:
        return _responder_previsao(exemplo, resultado)

    consulta = consultar_sql(exemplo.sql)
    resultado["sqls_executados"].append({"sql": exemplo.sql, "erro": consulta["erro"]})
    resultado["passos"].append({"tipo": "tool", "nome": "consultar_sql", "entrada": {"sql": exemplo.sql},
                                "erro": consulta["erro"]})
    if consulta["erro"]:
        resultado["resposta_texto"] = f"A consulta falhou: {consulta['erro']}"
        return resultado

    linhas = [dict(zip(consulta["colunas"], linha)) for linha in consulta["linhas"]]
    if exemplo.grafico:
        grafico = gerar_grafico(linhas, **exemplo.grafico)
        if not grafico["erro"]:
            resultado["graficos"].append(grafico["figura"])
            resultado["passos"].append({"tipo": "tool", "nome": "gerar_grafico",
                                        "entrada": {"tipo": exemplo.grafico["tipo"]}, "erro": None})

    resultado["n_iteracoes"] = len(resultado["passos"])
    resultado["resposta_texto"] = f"{exemplo.resumir(linhas)}\n\n{FONTE}\n\n{AVISO}"
    return resultado


def _responder_previsao(exemplo: Exemplo, resultado: dict[str, Any]) -> dict[str, Any]:
    a_id, b_id, superficie = exemplo.previsao
    entrada = {"jogador_a_id": a_id, "jogador_b_id": b_id, "superficie": superficie}
    previsao = prever_partida(**entrada)
    resultado["passos"].append({"tipo": "tool", "nome": "prever_partida", "entrada": entrada,
                                "erro": previsao["erro"]})
    if previsao["erro"]:
        resultado["resposta_texto"] = f"A previsão falhou: {previsao['erro']}"
        return resultado

    dados = [{"jogador": j["nome"], "chance (%)": round(100 * p, 1)}
             for j, p in ((previsao["jogador_a"], previsao["prob_a"]), (previsao["jogador_b"], previsao["prob_b"]))]
    grafico = gerar_grafico(dados, "barra", "jogador", "chance (%)", "Chance de vitória pelo Elo (%)")
    if not grafico["erro"]:
        resultado["graficos"].append(grafico["figura"])
    resultado["n_iteracoes"] = len(resultado["passos"])
    resultado["resposta_texto"] = f"{exemplo.resumir([previsao])}\n\n{FONTE}\n\n{AVISO}"
    return resultado
