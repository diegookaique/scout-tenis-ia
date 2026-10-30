"""Interface Streamlit do Scout de Tênis IA.

Uso:
    streamlit run app.py

A IA vem da Gemini API (GEMINI_API_KEY, plano gratuito) ou da Claude API (ANTHROPIC_API_KEY).
Sem chave, o app abre em modo demonstração (só as perguntas de exemplo).
"""

import os
from pathlib import Path
from typing import Any

import plotly.io as pio
import streamlit as st
from dotenv import load_dotenv

from src.db import cursor
from src.demo import GRUPOS_EXEMPLO, ICONES_EXEMPLO, AgenteDemo
from src.preparo import banco_pronto, preparar_banco
from src.provedores import NOMES, VARIAVEIS, criar_agente, descrever_erro, escolher_provedor

load_dotenv()

URL_GITHUB = "https://github.com/diegookaique/scout-tenis-ia"
URL_DADOS = "https://github.com/JeffSackmann/tennis_atp"
CAMINHO_CSS = Path(__file__).parent / "assets" / "estilo.css"
ICONES_GRUPO = {"Previsões 2026": ":material/insights:", "Temporada em números": ":material/leaderboard:"}
SUBTITULOS_GRUPO = {
    "Previsões 2026": "Elo por superfície e simulação de torneios",
    "Temporada em números": "O que já aconteceu no circuito",
}

# Cores que mudam com o tema (o restante do estilo fica em assets/estilo.css)
CORES_TEMA = {
    "light": {"card": "#FFFFFF", "borda": "#D5DFD1", "texto": "#132018", "texto-suave": "#55665A",
              "acento": "#15803D", "no-acento": "#FFFFFF", "acento-suave": "rgba(21, 128, 61, 0.08)",
              "acento-borda": "rgba(21, 128, 61, 0.30)",
              "sombra": "0 1px 2px rgba(16, 40, 24, 0.05), 0 4px 14px rgba(16, 40, 24, 0.05)"},
    "dark": {"card": "#111C16", "borda": "#25362C", "texto": "#E6EEE8", "texto-suave": "#9AAEA1",
             "acento": "#A3E635", "no-acento": "#0B130F", "acento-suave": "rgba(163, 230, 53, 0.08)",
             "acento-borda": "rgba(163, 230, 53, 0.30)", "sombra": "none"},
}

st.set_page_config(page_title="Scout de Tênis IA", page_icon="🎾", layout="wide",
                   initial_sidebar_state="collapsed")


# ---------------------------------------------------------------- banco


@st.cache_resource(show_spinner="Preparando o banco de dados pela primeira vez: baixando 79 mil partidas "
                                "e calculando o Elo. Leva cerca de 1 a 2 minutos e só acontece uma vez.")
def garantir_banco() -> None:
    """No servidor o banco não vem do GitHub: monta na primeira visita (uma vez por servidor)."""
    if not banco_pronto():
        preparar_banco()


# ---------------------------------------------------------------- agente


def _segredo(nome: str) -> str:
    """Valor de st.secrets no deploy ou do .env no computador. Vazio se não houver."""
    try:
        valor = st.secrets.get(nome, "")
    except Exception:  # sem secrets.toml o Streamlit levanta erro ao acessar st.secrets
        valor = ""
    return valor or os.getenv(nome, "")


def ler_provedor() -> tuple[str, str]:
    """(provedor, chave): Gemini, Claude ou "demo" quando não há chave."""
    chaves = {var: _segredo(var) for var in VARIAVEIS.values()}
    return escolher_provedor(chaves, _segredo("PROVEDOR"))


@st.cache_resource(show_spinner=False)
def carregar_agente(provedor: str, chave: str) -> Any:
    """Agente do provedor escolhido; sem chave, o modo demonstração."""
    return criar_agente(provedor, chave)


@st.cache_data(show_spinner=False)
def numeros_dos_dados() -> dict[str, Any]:
    partidas, jogadores, inicio, fim = cursor().execute("""
        SELECT count(*) // 2, count(DISTINCT player_id), min(data), max(data) FROM partidas_jogador
    """).fetchone()
    lider, pontos, data_ranking = cursor().execute("""
        SELECT j.nome_completo, r.pontos, r.data_ranking
        FROM rankings r JOIN jogadores j USING (player_id)
        WHERE r.posicao = 1 ORDER BY r.data_ranking DESC LIMIT 1
    """).fetchone()
    return {"partidas": partidas, "jogadores": jogadores, "inicio": inicio, "fim": fim,
            "lider": lider, "pontos_lider": pontos, "data_ranking": data_ranking}


def _milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


# ---------------------------------------------------------------- estado


def iniciar_estado() -> None:
    st.session_state.setdefault("mensagens", [])  # o que aparece na tela
    st.session_state.setdefault("historico", [])  # o que o agente recebe de contexto


def limpar_conversa() -> None:
    st.session_state.mensagens = []
    st.session_state.historico = []


# ---------------------------------------------------------------- estilo


def aplicar_estilo() -> None:
    """Injeta o CSS do app com as cores do tema ativo (claro ou escuro)."""
    try:
        tema = st.context.theme.type or "light"
    except Exception:  # versões sem st.context.theme
        tema = "light"
    variaveis = "".join(f"--sc-{nome}: {valor};" for nome, valor in CORES_TEMA[tema].items())
    st.markdown(f"<style>:root {{{variaveis}}}\n{CAMINHO_CSS.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------- exibição


def mostrar_resposta(msg: dict[str, Any], indice: int) -> None:
    st.markdown(msg["texto"])
    for n, figura in enumerate(msg.get("graficos", [])):
        st.plotly_chart(pio.from_json(figura), use_container_width=True, key=f"grafico-{indice}-{n}")
    if msg.get("sqls") or msg.get("passos"):
        with st.expander("Como cheguei nisso", icon=":material/manage_search:"):
            mostrar_passos(msg.get("passos", []))
            for n, item in enumerate(msg.get("sqls", []), start=1):
                st.caption(f"Consulta {n}" + (" (falhou; o agente leu o erro e tentou de novo)" if item["erro"] else ""))
                st.code(item["sql"], language="sql")
                if item["erro"]:
                    st.caption(f"Erro: {item['erro']}")


def mostrar_passos(passos: list[dict[str, Any]]) -> None:
    linhas = []
    for passo in passos:
        if passo["tipo"] == "pensamento":
            linhas.append(f"- 💭 {passo['texto']}")
        elif passo["tipo"] == "tool" and passo["nome"] != "consultar_sql":
            entrada = ", ".join(f"{k}={v}" for k, v in passo["entrada"].items())
            linhas.append(f"- 🛠️ `{passo['nome']}({entrada})`" + (" ✗" if passo.get("erro") else ""))
    if linhas:
        st.markdown("\n".join(linhas))


def mostrar_conversa() -> None:
    for i, msg in enumerate(st.session_state.mensagens):
        with st.chat_message(msg["papel"], avatar="🎾" if msg["papel"] == "assistant" else ":material/person:"):
            if msg["papel"] == "user":
                st.markdown(msg["texto"])
            else:
                mostrar_resposta(msg, i)


# ---------------------------------------------------------------- perguntar


def responder(agente: Any, pergunta: str) -> None:
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(pergunta)

    with st.chat_message("assistant", avatar="🎾"):
        with st.spinner("Analisando os dados..."):
            try:
                r = agente.perguntar(pergunta, st.session_state.historico)
            except Exception as erro:  # o app não deve quebrar por um erro de API ou inesperado
                r = _resposta_reserva(pergunta, erro)
        msg = {"papel": "assistant", "texto": r["resposta_texto"], "graficos": r["graficos"],
               "sqls": r["sqls_executados"], "passos": r["passos"]}
        st.session_state.mensagens.append(msg)
        st.session_state.historico = r["historico"]
        mostrar_resposta(msg, len(st.session_state.mensagens) - 1)


def _resposta_reserva(pergunta: str, erro: Exception) -> dict[str, Any]:
    """Se a IA falhar (ex.: limite gratuito) numa pergunta de exemplo, usa a resposta pronta."""
    mensagem = descrever_erro(erro)
    if mensagem and pergunta in ICONES_EXEMPLO:
        r = AgenteDemo().perguntar(pergunta)
        r["resposta_texto"] = f"_{mensagem} Enquanto isso, a resposta pronta deste exemplo:_\n\n{r['resposta_texto']}"
        r["historico"] = st.session_state.historico
        return r
    return _falha(mensagem or f"Algo deu errado ao responder: {erro}")


def _falha(texto: str) -> dict[str, Any]:
    return {"resposta_texto": f"⚠️ {texto}", "graficos": [], "sqls_executados": [], "passos": [],
            "historico": st.session_state.historico}


# ---------------------------------------------------------------- tela inicial


def topo(ia: str, modo_demo: bool) -> None:
    """Faixa de destaque com o nome, o que o app faz e os números principais."""
    n = numeros_dos_dados()
    chips = [f"{_milhar(n['partidas'])} partidas", f"{n['inicio'].year}–{n['fim'].year}",
             "Elo validado: 64,2% de acerto", f"IA: {ia}"]
    st.markdown(f"""
<div class="sc-hero">
  <div class="sc-hero-quadra"></div><div class="sc-bola"></div>
  <div class="sc-hero-conteudo">
    <span class="sc-selo">Agente de IA · dados reais da ATP</span>
    <div class="sc-titulo">Scout de <span>Tênis</span> IA</div>
    <p>Pergunte sobre o circuito masculino em português. O agente encontra os jogadores, escreve o
    SQL, calcula a resposta e mostra o gráfico. Também prevê partidas e torneios com Elo por superfície.</p>
    <div class="sc-chips">{"".join(f"<span>{c}</span>" for c in chips)}</div>
  </div>
</div>""", unsafe_allow_html=True)
    if modo_demo:
        st.markdown("""
<div class="sc-aviso"><span>ℹ️</span><div><b>Modo demonstração.</b> O app está sem chave de IA: as 10
perguntas abaixo são respondidas com consultas prontas, no mesmo banco e com as mesmas ferramentas.
Perguntas livres precisam da IA.</div></div>""", unsafe_allow_html=True)


def numeros() -> None:
    n = numeros_dos_dados()
    cartoes = [
        ("Partidas da ATP", _milhar(n["partidas"]), "circuito principal"),
        ("Jogadores", _milhar(n["jogadores"]), "com partida registrada"),
        ("Período", f"{n['inicio'].year}–{n['fim'].year}", f"até {n['fim']:%d/%m/%Y}"),
    ]
    html = "".join(f'<div class="sc-numero"><small>{t}</small><b>{v}</b><span>{s}</span></div>' for t, v, s in cartoes)
    lider = (f'<div class="sc-numero destaque"><small>Nº 1 do ranking</small><b>{n["lider"]}</b>'
             f'<span>{_milhar(n["pontos_lider"])} pontos · {n["data_ranking"]:%d/%m/%Y}</span></div>')
    st.markdown(f'<div class="sc-numeros">{html}{lider}</div>', unsafe_allow_html=True)


def exemplos() -> str | None:
    """As 10 perguntas de exemplo em duas colunas de 5; devolve a clicada."""
    st.markdown('<div class="sc-secao">Experimente</div>'
                '<p class="sc-secao-sub">Clique numa pergunta ou escreva a sua no campo do topo.</p>',
                unsafe_allow_html=True)
    clicada = None
    for n, (coluna, (grupo, perguntas)) in enumerate(zip(st.columns(2, gap="large"), GRUPOS_EXEMPLO.items())):
        with coluna:
            st.markdown(f'<div class="sc-grupo">{grupo}</div>', unsafe_allow_html=True)
            st.caption(SUBTITULOS_GRUPO[grupo])
            with st.container(key=f"grupo-{n}"):
                for i, pergunta in enumerate(perguntas):
                    if st.button(pergunta, key=f"inicio-{n}-{i}", icon=ICONES_EXEMPLO[pergunta], width="stretch"):
                        clicada = pergunta
    return clicada


def como_funciona() -> None:
    passos = [
        ("Você pergunta", "Em português, do jeito que falaria com um analista."),
        ("A IA consulta o banco", "Busca os jogadores e escreve SQL de leitura no DuckDB com 79 mil partidas."),
        ("Resposta com prova", "Texto, gráfico e o SQL usado, em “Como cheguei nisso”."),
    ]
    html = "".join(f'<div class="sc-passo"><i>{n}</i><b>{t}</b>{d}</div>' for n, (t, d) in enumerate(passos, 1))
    st.markdown(f'<div class="sc-passos">{html}</div>', unsafe_allow_html=True)


def cabecalho_compacto() -> None:
    """Durante a conversa: nome do app e botão de nova conversa."""
    texto, botao = st.columns([4, 1.3], vertical_alignment="center")
    texto.markdown('<div class="sc-compacto"><div class="sc-bola-mini"></div><div><b>Scout de Tênis IA</b>'
                   '<small>Circuito masculino (ATP) · dados reais consultados com SQL</small></div></div>',
                   unsafe_allow_html=True)
    botao.button("Nova conversa", icon=":material/add_comment:", on_click=limpar_conversa, width="stretch")


def rodape() -> None:
    st.markdown(f"""
<div class="sc-rodape">Dados de <a href="{URL_DADOS}" target="_blank">Jeff Sackmann / tennis_atp</a>
(CC BY-NC-SA 4.0) · <a href="{URL_GITHUB}" target="_blank">código no GitHub</a> ·
projeto de portfólio, sem vínculo com a ATP</div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- barra lateral


def barra_lateral(ia: str) -> str | None:
    """Desenha a barra lateral e devolve a pergunta de exemplo clicada, se houver."""
    clicada = None
    with st.sidebar:
        st.markdown('<div class="sc-lateral-marca"><span>🎾</span><b>Scout de Tênis IA</b></div>',
                    unsafe_allow_html=True)
        for n, (grupo, perguntas) in enumerate(GRUPOS_EXEMPLO.items()):
            st.markdown(f'<div class="sc-grupo">{grupo}</div>', unsafe_allow_html=True)
            for i, pergunta in enumerate(perguntas):
                if st.button(pergunta, key=f"lateral-{n}-{i}", icon=ICONES_EXEMPLO[pergunta], width="stretch",
                             type="tertiary"):
                    clicada = pergunta

        st.divider()
        n = numeros_dos_dados()
        st.markdown(f"**Dados:** partidas da ATP de {n['inicio']:%d/%m/%Y} a {n['fim']:%d/%m/%Y}.")
        st.caption("Circuito principal: Grand Slams, Masters, ATP 250/500, Finals, Copa Davis e Olimpíadas.")
        st.markdown(f"**IA:** {ia}")
        st.link_button("Código no GitHub", URL_GITHUB, icon=":material/code:", width="stretch")
        st.button("Limpar conversa", icon=":material/delete:", on_click=limpar_conversa, width="stretch")
    return clicada


# ---------------------------------------------------------------- página


def main() -> None:
    iniciar_estado()
    aplicar_estilo()
    try:
        garantir_banco()
    except Exception as erro:
        st.error(f"Não foi possível preparar o banco de dados ({type(erro).__name__}: {erro}). "
                 "Recarregue a página em alguns minutos.")
        st.stop()
    provedor, chave = ler_provedor()
    agente = carregar_agente(provedor, chave)
    modo_demo = isinstance(agente, AgenteDemo)
    ia = "modo demonstração" if modo_demo else NOMES[provedor].split(" (")[0].replace(" API", "")

    # Pergunta clicada na tela inicial: volta a desenhar a página já sem a tela inicial
    pendente = st.session_state.pop("pendente", None)
    clicada = barra_lateral(NOMES[provedor] + ("" if modo_demo else f" · `{agente.modelo}`"))
    dica = "Escolha um exemplo ou digite" if modo_demo else "Pergunte sobre tênis: jogadores, torneios, previsões..."
    if not st.session_state.mensagens and not pendente:
        topo(ia, modo_demo)
        # Na tela inicial o campo fica no corpo da página, logo abaixo do topo: o Streamlit
        # rola a página até o campo ao abrir, então ele precisa estar visível de cara
        with st.container(key="campo-inicio"):
            digitada = st.chat_input(dica, key="pergunta-inicio")
        numeros()
        inicial = exemplos()
        como_funciona()
        rodape()
        if inicial or digitada or clicada:
            st.session_state.pendente = inicial or digitada or clicada
            st.rerun()
        return
    cabecalho_compacto()
    mostrar_conversa()
    digitada = st.chat_input(dica, key="pergunta-conversa")
    pergunta = pendente or clicada or digitada
    if pergunta:
        responder(agente, pergunta)


main()
