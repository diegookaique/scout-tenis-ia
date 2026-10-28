"""Interface Streamlit do Scout de Tênis IA.

Uso:
    streamlit run app.py

Sem chave da Claude API, o app abre em modo demonstração (só as perguntas de exemplo).
"""

import os
from typing import Any

import anthropic
import plotly.io as pio
import streamlit as st
from dotenv import load_dotenv

from src.db import cursor
from src.demo import PERGUNTAS_EXEMPLO, AgenteDemo

load_dotenv()

URL_GITHUB = "https://github.com/diegookaique/scout-tenis-ia"
CHAVE_EXEMPLO = "sua-chave-aqui"

st.set_page_config(page_title="Scout de Tênis IA", page_icon="🎾", layout="wide",
                   initial_sidebar_state="collapsed")


# ---------------------------------------------------------------- agente


def ler_chave() -> str:
    """Chave da API: st.secrets no deploy, .env no computador. Vazia se não houver."""
    try:
        chave = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:  # sem secrets.toml o Streamlit levanta erro ao acessar st.secrets
        chave = ""
    chave = chave or os.getenv("ANTHROPIC_API_KEY", "")
    return "" if chave == CHAVE_EXEMPLO else chave


@st.cache_resource(show_spinner=False)
def carregar_agente(chave: str) -> Any:
    """Agente real quando há chave; senão, o modo demonstração."""
    if not chave:
        return AgenteDemo()
    from src.agente import AgenteTenis

    return AgenteTenis(client=anthropic.Anthropic(api_key=chave))


@st.cache_data(show_spinner=False)
def periodo_dos_dados() -> tuple[str, str]:
    inicio, fim = cursor().execute("SELECT min(tourney_date), max(tourney_date) FROM partidas").fetchone()
    return inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")


@st.cache_data(show_spinner=False)
def numeros_dos_dados() -> dict[str, int]:
    partidas, jogadores, torneios = cursor().execute("""
        SELECT count(*), count(DISTINCT player_id), count(DISTINCT torneio_id)
        FROM partidas_jogador
    """).fetchone()
    return {"partidas": partidas // 2, "jogadores": jogadores, "torneios": torneios}


def _milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


# ---------------------------------------------------------------- estado


def iniciar_estado() -> None:
    st.session_state.setdefault("mensagens", [])  # o que aparece na tela
    st.session_state.setdefault("historico", [])  # o que o agente recebe de contexto


def limpar_conversa() -> None:
    st.session_state.mensagens = []
    st.session_state.historico = []


# ---------------------------------------------------------------- exibição


def mostrar_resposta(msg: dict[str, Any], indice: int) -> None:
    st.markdown(msg["texto"])
    for n, figura in enumerate(msg.get("graficos", [])):
        st.plotly_chart(pio.from_json(figura), use_container_width=True, key=f"grafico-{indice}-{n}")
    if msg.get("sqls") or msg.get("passos"):
        with st.expander("🔍 Como cheguei nisso"):
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
        with st.chat_message(msg["papel"], avatar="🎾" if msg["papel"] == "assistant" else None):
            if msg["papel"] == "user":
                st.markdown(msg["texto"])
            else:
                mostrar_resposta(msg, i)


# ---------------------------------------------------------------- perguntar


def responder(agente: Any, pergunta: str) -> None:
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant", avatar="🎾"):
        with st.spinner("Analisando os dados..."):
            try:
                r = agente.perguntar(pergunta, st.session_state.historico)
            except anthropic.AuthenticationError:
                r = _falha("A chave da Claude API foi recusada. Confira o valor de ANTHROPIC_API_KEY.")
            except anthropic.APIError as erro:
                r = _falha(f"A Claude API não respondeu agora ({type(erro).__name__}). Tente de novo em instantes.")
            except Exception as erro:  # o app não deve quebrar por um erro inesperado
                r = _falha(f"Algo deu errado ao responder: {erro}")
        msg = {"papel": "assistant", "texto": r["resposta_texto"], "graficos": r["graficos"],
               "sqls": r["sqls_executados"], "passos": r["passos"]}
        st.session_state.mensagens.append(msg)
        st.session_state.historico = r["historico"]
        mostrar_resposta(msg, len(st.session_state.mensagens) - 1)


def _falha(texto: str) -> dict[str, Any]:
    return {"resposta_texto": f"⚠️ {texto}", "graficos": [], "sqls_executados": [], "passos": [],
            "historico": st.session_state.historico}


# ---------------------------------------------------------------- tela inicial


def boas_vindas() -> str | None:
    """Tela antes da primeira pergunta: o que o app faz, números e exemplos clicáveis."""
    numeros = numeros_dos_dados()
    inicio, fim = periodo_dos_dados()
    st.markdown(
        "O Scout encontra os jogadores, escreve a consulta SQL, calcula a resposta e mostra um "
        "gráfico. Ele também prevê partidas com um **rating Elo por superfície**. Abra "
        "**🔍 Como cheguei nisso** em qualquer resposta para ver o SQL usado."
    )
    colunas = st.columns(3)
    colunas[0].metric("Partidas da ATP", _milhar(numeros["partidas"]))
    colunas[1].metric("Jogadores", _milhar(numeros["jogadores"]))
    colunas[2].metric("Período", f"{inicio[-4:]}–{fim[-4:]}")

    st.markdown("##### Experimente")
    clicada = None
    grade = st.columns(2)
    for n, pergunta in enumerate(PERGUNTAS_EXEMPLO):
        if grade[n % 2].button(pergunta, key=f"inicio-{n}", use_container_width=True):
            clicada = pergunta
    return clicada


# ---------------------------------------------------------------- barra lateral


def barra_lateral() -> str | None:
    """Desenha a barra lateral e devolve a pergunta de exemplo clicada, se houver."""
    clicada = None
    with st.sidebar:
        st.subheader("Perguntas de exemplo")
        for n, pergunta in enumerate(PERGUNTAS_EXEMPLO):
            if st.button(pergunta, key=f"exemplo-{n}", use_container_width=True):
                clicada = pergunta

        st.divider()
        inicio, fim = periodo_dos_dados()
        st.markdown(f"**Dados:** partidas da ATP de {inicio} a {fim}.")
        st.caption("Circuito principal: Grand Slams, Masters, ATP 250/500, Finals, Copa Davis e Olimpíadas.")
        if URL_GITHUB:
            st.markdown(f"[Código no GitHub]({URL_GITHUB})")

        st.divider()
        st.button("🗑️ Limpar conversa", on_click=limpar_conversa, use_container_width=True)
    return clicada


# ---------------------------------------------------------------- página


def main() -> None:
    iniciar_estado()
    agente = carregar_agente(ler_chave())
    modo_demo = isinstance(agente, AgenteDemo)

    st.title("🎾 Scout de Tênis IA")
    st.caption("Pergunte sobre o circuito masculino de tênis. As respostas vêm de dados reais da ATP "
               "(Jeff Sackmann / tennis_atp), consultados com SQL.")

    if modo_demo:
        st.info("**Modo demonstração:** este app está sem chave da Claude API. As perguntas de "
                "exemplo funcionam com consultas prontas; perguntas livres precisam da IA.", icon="ℹ️")

    # Pergunta clicada na tela inicial: volta a desenhar a página já sem a tela inicial
    pendente = st.session_state.pop("pendente", None)
    clicada = barra_lateral()
    if not st.session_state.mensagens and not pendente:
        inicial = boas_vindas()
        if inicial:
            st.session_state.pendente = inicial
            st.rerun()
    mostrar_conversa()
    dica = "Escolha um exemplo ou digite" if modo_demo else "Pergunte sobre tênis..."
    digitada = st.chat_input(dica)
    pergunta = pendente or clicada or digitada
    if pergunta:
        responder(agente, pergunta)


main()
