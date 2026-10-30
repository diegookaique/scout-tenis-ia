"""Modo demonstração: responde as perguntas de exemplo sem chamar nenhuma API de IA.

Cada exemplo segue o mesmo caminho do agente (buscar_jogador → consultar_sql →
gerar_grafico) com consultas prontas, e devolve o mesmo formato de resultado de
AgenteTenis.perguntar. Serve para usar a interface sem chave da API.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.tools import buscar_jogador, consultar_sql, gerar_grafico, prever_partida, simular_torneio

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
    grupo: str = ""
    icone: str = ""  # ícone Material do botão na interface
    # Exemplos de previsão chamam prever_partida(a, b, superfície) em vez de SQL
    previsao: tuple[int, int, str] | None = None
    # Exemplos de torneio: o SQL devolve os participantes e simular_torneio roda nesta superfície
    torneio: str | None = None


def _num(valor: float, casas: int = 0) -> str:
    """Formata no padrão brasileiro: 1.260 e 79,5."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- resumos


def _lista(itens: list[str]) -> str:
    """["a", "b", "c"] -> "a, b e c"."""
    return " e ".join([", ".join(itens[:-1]), itens[-1]]) if len(itens) > 1 else "".join(itens)


def _data_br(iso: str) -> str:
    ano, mes, dia = iso[:10].split("-")
    return f"{dia}/{mes}/{ano}"


def _resumo_finals(dados: dict[str, Any]) -> str:
    j = dados["jogadores"]
    top = j[0]
    resto = ", ".join(f"{x['nome']} ({_num(100 * x['prob_titulo'], 1)}%)" for x in j[1:4])
    avisos = "\n".join(f"- {a}" for a in dados["avisos"])
    return (f"**{top['nome']}** é o favorito ao título do ATP Finals 2026, com **{_num(100 * top['prob_titulo'], 1)}%** "
            f"de chance (chega à final em {_num(100 * top['prob_final'], 1)}% das simulações).\n\n"
            f"Na sequência: {resto}.\n\n"
            f"Classificados: os 8 primeiros do ranking de {_data_br(dados['data_ranking'])}, em quadra dura, no formato "
            f"do torneio (2 grupos de 4, semifinais cruzadas e final).\n\n**Avisos:**\n{avisos}")


def _resumo_numero1(linhas: list[dict[str, Any]]) -> str:
    lider, vice = linhas[0], linhas[1]
    criterios = (("pontos", "pontos"), ("aproveitamento", "pct_vitorias"), ("títulos", "titulos"), ("Elo", "elo"))
    lidera = [nome for nome, coluna in criterios if lider[coluna] == max(l[coluna] or 0 for l in linhas)]
    return (f"**{lider['jogador']}** é o favorito para terminar 2026 como número 1: lidera em "
            f"{_lista(lidera)} entre os 5 primeiros do ranking.\n\n"
            f"- Ranking: **{_num(lider['pontos'])} pontos**, {_num(lider['pontos'] - vice['pontos'])} à frente "
            f"de {vice['jogador']} ({_num(vice['pontos'])})\n"
            f"- Temporada 2026: {lider['vitorias']} vitórias e {lider['derrotas']} derrotas "
            f"({_num(lider['pct_vitorias'], 1)}%), {lider['titulos']} títulos\n"
            f"- Elo geral: {_num(lider['elo'])} (o de {vice['jogador']} é {_num(vice['elo'])})\n\n"
            f"Ranking de {_data_br(lider['data_ranking'])}: ainda falta metade da temporada, então é uma "
            "tendência, não uma certeza.")


def _resumo_wimbledon(linhas: list[dict[str, Any]]) -> str:
    a, b = linhas[0], linhas[1]
    resto = ", ".join(f"{l['jogador']} ({_num(l['elo_grama_combinado'])})" for l in linhas[2:5])
    diferenca = a["elo_grama_combinado"] - b["elo_grama_combinado"]
    disputa = "quase empatados" if diferenca < 25 else f"com {a['jogador']} {_num(diferenca)} pontos à frente"
    return (f"Pelo Elo de grama, **{a['jogador']}** ({_num(a['elo_grama_combinado'])}) e **{b['jogador']}** "
            f"({_num(b['elo_grama_combinado'])}) chegam como favoritos, {disputa}.\n\n"
            f"Na sequência: {resto}.\n\n"
            "O Elo combinado é a média do Elo geral com o da grama. Só entram jogadores com partida em 2026. "
            "A grama tem poucos torneios por ano, então o Elo dela muda mais devagar.")


def _resumo_revelacoes(linhas: list[dict[str, Any]]) -> str:
    top = linhas[0]
    resto = ", ".join(f"{l['jogador']} (+{_num(l['ganho'])})" for l in linhas[1:5])
    return (f"A maior revelação de 2026 é **{top['jogador']}**: o Elo dele subiu **{_num(top['ganho'])} pontos** "
            f"(de {_num(top['elo_inicio'])} para {_num(top['elo_atual'])}) em {top['partidas_2026']} partidas.\n\n"
            f"Também subiram muito: {resto}.\n\n"
            "Conta só quem jogou pelo menos 10 partidas no circuito principal em 2026.")


def _resumo_aproveitamento(linhas: list[dict[str, Any]]) -> str:
    top = linhas[0]
    resto = ", ".join(f"{l['jogador']} ({_num(l['pct_vitorias'], 1)}%)" for l in linhas[1:5])
    return (f"**{top['jogador']}**, com **{_num(top['pct_vitorias'], 1)}%** de vitórias em 2026 "
            f"({top['vitorias']} vitórias em {top['partidas']} partidas).\n\n"
            f"Na sequência: {resto}.\n\nSó entram jogadores com pelo menos 15 partidas no ano.")


def _resumo_aces(linhas: list[dict[str, Any]]) -> str:
    top = linhas[0]
    resto = ", ".join(f"{l['jogador']} ({_num(l['aces'])})" for l in linhas[1:5])
    return (f"**{top['jogador']}**, com **{_num(top['aces'])} aces** em 2026 "
            f"({_num(top['aces'] / top['partidas'], 1)} por partida).\n\nNa sequência: {resto}.\n\n"
            "A soma só conta partidas com estatística de saque.")


def _resumo_h2h(linhas: list[dict[str, Any]]) -> str:
    sinner = sum(l["vitorias_sinner"] for l in linhas)
    alcaraz = sum(l["vitorias_alcaraz"] for l in linhas)
    lider = "Alcaraz" if alcaraz > sinner else "Sinner"
    por_sup = "; ".join(f"{l['superficie']}: {l['vitorias_sinner']}–{l['vitorias_alcaraz']}" for l in linhas)
    return (f"**Sinner {sinner} × {alcaraz} Alcaraz** no circuito principal, com vantagem de {lider}.\n\n"
            f"Por superfície (Sinner–Alcaraz): {por_sup}.")


def _resumo_fonseca(linhas: list[dict[str, Any]]) -> str:
    melhor = min(linhas, key=lambda l: (l["posicao"], l["data"]))
    inicio, atual = linhas[0], linhas[-1]
    return (f"João Fonseca saiu do **{inicio['posicao']}º lugar** ({_data_br(inicio['data'])}) para o "
            f"**{atual['posicao']}º** ({_data_br(atual['data'])}), com {_num(atual['pontos'])} pontos.\n\n"
            f"Melhor posição: **{melhor['posicao']}º**, em {_data_br(melhor['data'])}. "
            "O gráfico mostra os pontos no ranking semana a semana.")


def _resumo_evolucao_elo(linhas: list[dict[str, Any]]) -> str:
    ultimo_ano = max(l["ano"] for l in linhas)
    atuais = sorted((l for l in linhas if l["ano"] == ultimo_ano), key=lambda l: l["elo"], reverse=True)
    seguintes = ", ".join(f"{l['jogador']} ({_num(l['elo'])})" for l in atuais[1:])
    picos = []
    for jogador in sorted({l["jogador"] for l in linhas}):
        pico = max((l for l in linhas if l["jogador"] == jogador), key=lambda l: l["elo"])
        picos.append(f"{jogador}: {_num(pico['elo'])} em {pico['ano']}")
    return (f"Em {ultimo_ano}, **{atuais[0]['jogador']}** tem o maior Elo ({_num(atuais[0]['elo'])}), "
            f"seguido de {seguintes}.\n\n"
            f"Pico de cada um desde 2018: {'; '.join(picos)}.\n\n"
            "O gráfico mostra o Elo geral no fim de cada ano (em 2026, o mais recente).")


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

PREVISOES = "Previsões 2026"
TEMPORADA = "Temporada em números"
ULTIMO_RANKING = "(SELECT max(data_ranking) FROM rankings)"

EXEMPLOS: list[Exemplo] = [
    # ------------------------------------------------ previsões
    Exemplo(
        grupo=PREVISOES,
        pergunta="Quem vai ganhar o ATP Finals de 2026?",
        icone=":material/emoji_events:",
        jogadores=[],
        sql=f"""SELECT player_id, posicao, data_ranking
FROM rankings
WHERE data_ranking = {ULTIMO_RANKING} AND posicao <= 8
ORDER BY posicao""",
        resumir=_resumo_finals,
        torneio="Hard",
    ),
    Exemplo(
        grupo=PREVISOES,
        pergunta="Quem vai terminar 2026 como número 1?",
        icone=":material/military_tech:",
        jogadores=[],
        sql=f"""WITH ranking AS (
    SELECT player_id, posicao, pontos, data_ranking FROM rankings
    WHERE data_ranking = {ULTIMO_RANKING} AND posicao <= 5
), temporada AS (
    SELECT player_id, count(*) AS partidas,
           count(*) FILTER (WHERE venceu) AS vitorias,
           count(*) FILTER (WHERE venceu AND rodada = 'F') AS titulos
    FROM partidas_jogador WHERE ano = 2026 GROUP BY player_id
)
SELECT r.posicao, j.nome_completo AS jogador, r.pontos,
       t.vitorias, t.partidas - t.vitorias AS derrotas,
       round(100.0 * t.vitorias / t.partidas, 1) AS pct_vitorias,
       t.titulos, round(e.rating) AS elo, r.data_ranking
FROM ranking r
JOIN jogadores j USING (player_id)
LEFT JOIN temporada t USING (player_id)
LEFT JOIN elo_atual e ON e.player_id = r.player_id AND e.superficie = 'Geral'
ORDER BY r.posicao""",
        resumir=_resumo_numero1,
        grafico={"tipo": "barra", "x": "jogador", "y": "pontos", "titulo": "Top 5 do ranking: pontos"},
    ),
    Exemplo(
        grupo=PREVISOES,
        pergunta="Quem é o favorito para Wimbledon 2026?",
        icone=":material/grass:",
        jogadores=[],
        sql="""SELECT j.nome_completo AS jogador,
       round((g.rating + s.rating) / 2) AS elo_grama_combinado,
       s.partidas AS partidas_na_grama
FROM elo_atual g
JOIN elo_atual s ON s.player_id = g.player_id AND s.superficie = 'Grass'
JOIN jogadores j ON j.player_id = g.player_id
WHERE g.superficie = 'Geral' AND g.ultima_partida >= DATE '2026-01-01'
ORDER BY elo_grama_combinado DESC LIMIT 8""",
        resumir=_resumo_wimbledon,
        grafico={"tipo": "barra", "x": "jogador", "y": "elo_grama_combinado",
                 "titulo": "Top 8 Elo na grama (geral + grama)"},
    ),
    Exemplo(
        grupo=PREVISOES,
        pergunta="Sinner × Alcaraz no saibro: quem é favorito?",
        icone=":material/sports_tennis:",
        jogadores=["Sinner", "Alcaraz"],
        sql="",
        resumir=_resumo_previsao,
        previsao=(206173, 207989, "Clay"),
    ),
    Exemplo(
        grupo=PREVISOES,
        pergunta="Quem são as revelações de 2026?",
        icone=":material/rocket_launch:",
        jogadores=[],
        sql="""WITH geral AS (SELECT * FROM elo WHERE superficie = 'Geral'),
inicio AS (
    SELECT player_id, arg_max(rating, partidas) AS elo_inicio
    FROM geral WHERE data < DATE '2026-01-01' GROUP BY player_id
),
atual AS (
    SELECT player_id, arg_max(rating, partidas) AS elo_atual,
           count(*) FILTER (WHERE year(data) = 2026) AS partidas_2026
    FROM geral GROUP BY player_id
)
SELECT j.nome_completo AS jogador, round(i.elo_inicio) AS elo_inicio, round(a.elo_atual) AS elo_atual,
       round(a.elo_atual - i.elo_inicio) AS ganho, a.partidas_2026
FROM atual a JOIN inicio i USING (player_id) JOIN jogadores j USING (player_id)
WHERE a.partidas_2026 >= 10
ORDER BY ganho DESC LIMIT 8""",
        resumir=_resumo_revelacoes,
        grafico={"tipo": "barra", "x": "jogador", "y": "ganho", "titulo": "Quem mais subiu no Elo em 2026"},
    ),
    # ------------------------------------------------ temporada
    Exemplo(
        grupo=TEMPORADA,
        pergunta="Quem tem o melhor aproveitamento em 2026?",
        icone=":material/trending_up:",
        jogadores=[],
        sql="""SELECT any_value(nome) AS jogador, count(*) AS partidas,
       count(*) FILTER (WHERE venceu) AS vitorias,
       round(100.0 * count(*) FILTER (WHERE venceu) / count(*), 1) AS pct_vitorias
FROM partidas_jogador
WHERE ano = 2026
GROUP BY player_id HAVING count(*) >= 15
ORDER BY pct_vitorias DESC LIMIT 10""",
        resumir=_resumo_aproveitamento,
        grafico={"tipo": "barra", "x": "jogador", "y": "pct_vitorias",
                 "titulo": "% de vitórias em 2026 (15+ partidas)"},
    ),
    Exemplo(
        grupo=TEMPORADA,
        pergunta="Quem fez mais aces em 2026?",
        icone=":material/bolt:",
        jogadores=[],
        sql="""SELECT any_value(nome) AS jogador, sum(aces) AS aces, count(aces) AS partidas
FROM partidas_jogador
WHERE ano = 2026
GROUP BY player_id ORDER BY aces DESC NULLS LAST LIMIT 10""",
        resumir=_resumo_aces,
        grafico={"tipo": "barra", "x": "jogador", "y": "aces", "titulo": "Top 10 em aces, 2026"},
    ),
    Exemplo(
        grupo=TEMPORADA,
        pergunta="Sinner × Alcaraz: como está o confronto direto?",
        icone=":material/swords:",
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
        grupo=TEMPORADA,
        pergunta="Como o João Fonseca evoluiu no ranking?",
        icone=":material/flag:",
        jogadores=["João Fonseca"],
        sql="""SELECT data_ranking AS data, posicao, pontos
FROM rankings
WHERE player_id = 211663 AND data_ranking >= DATE '2024-01-01'
ORDER BY data_ranking""",
        resumir=_resumo_fonseca,
        grafico={"tipo": "linha", "x": "data", "y": "pontos", "titulo": "João Fonseca: pontos no ranking"},
    ),
    Exemplo(
        grupo=TEMPORADA,
        pergunta="Como evoluiu o Elo de Sinner, Alcaraz e Djokovic?",
        icone=":material/show_chart:",
        jogadores=["Sinner", "Alcaraz", "Djokovic"],
        sql="""SELECT year(e.data) AS ano, any_value(j.nome_completo) AS jogador,
       round(arg_max(e.rating, e.partidas)) AS elo
FROM elo e JOIN jogadores j USING (player_id)
WHERE e.superficie = 'Geral' AND e.player_id IN (206173, 207989, 104925)
  AND year(e.data) >= 2018
GROUP BY e.player_id, year(e.data)
ORDER BY jogador, ano""",
        resumir=_resumo_evolucao_elo,
        grafico={"tipo": "linha", "x": "ano", "y": "elo", "serie": "jogador",
                 "titulo": "Elo geral no fim de cada ano: Sinner, Alcaraz e Djokovic"},
    ),
]

PERGUNTAS_EXEMPLO = [e.pergunta for e in EXEMPLOS]
ICONES_EXEMPLO = {e.pergunta: e.icone for e in EXEMPLOS}
GRUPOS_EXEMPLO = {grupo: [e.pergunta for e in EXEMPLOS if e.grupo == grupo] for grupo in (PREVISOES, TEMPORADA)}


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
                "Para perguntas livres, o app precisa de uma chave de IA: GEMINI_API_KEY "
                "(grátis em aistudio.google.com) ou ANTHROPIC_API_KEY."
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
    if exemplo.torneio:
        return _responder_torneio(exemplo, linhas, resultado)
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


def _responder_torneio(exemplo: Exemplo, linhas: list[dict[str, Any]], resultado: dict[str, Any]) -> dict[str, Any]:
    entrada = {"jogadores_ids": [l["player_id"] for l in linhas], "superficie": exemplo.torneio}
    simulacao = simular_torneio(**entrada)
    resultado["passos"].append({"tipo": "tool", "nome": "simular_torneio", "entrada": entrada,
                                "erro": simulacao["erro"]})
    if simulacao["erro"]:
        resultado["resposta_texto"] = f"A simulação falhou: {simulacao['erro']}"
        return resultado

    dados = [{"jogador": j["nome"], "título (%)": round(100 * j["prob_titulo"], 1)} for j in simulacao["jogadores"]]
    grafico = gerar_grafico(dados, "barra", "jogador", "título (%)", "Chance de título no ATP Finals 2026 (%)")
    if not grafico["erro"]:
        resultado["graficos"].append(grafico["figura"])
    resultado["n_iteracoes"] = len(resultado["passos"])
    resumo = exemplo.resumir({**simulacao, "data_ranking": linhas[0]["data_ranking"]})
    resultado["resposta_texto"] = f"{resumo}\n\n{FONTE}\n\n{AVISO}"
    return resultado
