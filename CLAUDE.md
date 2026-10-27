# Scout de Tênis IA

Agente de IA que responde perguntas sobre tênis (ATP) em linguagem natural, consultando um banco DuckDB via SQL e gerando gráficos. Projeto de portfólio.

## Contexto
- O roteiro completo, com as etapas e o progresso, está em `ROTEIRO.md`. Leia antes de começar cada tarefa.
- Dados: CSVs de github.com/JeffSackmann/tennis_atp, carregados em `tenis.duckdb` por `scripts/carregar_dados.py`.
- Stack: Python 3.11+, DuckDB, Anthropic SDK (tool use), Streamlit, Plotly.

## Comandos
- Instalar: `pip install -r requirements.txt`
- Carregar dados: `python scripts/carregar_dados.py` (já recalcula o Elo no fim)
- Só recalcular o Elo: `python scripts/calcular_elo.py`
- Agente no terminal: `python -m src.agente`
- App: `streamlit run app.py`
- Testes: `pytest`
- Avaliação: `python scripts/avaliar.py`

## Convenções
- Código, comentários, docstrings e mensagens ao usuário em **português**.
- Funções pequenas, com type hints.
- O agente só executa SQL de leitura (SELECT/WITH). Nunca remova essa trava.
- Nunca commitar `.env`, `data/` ou `*.duckdb`.
- A chave da API vem de `ANTHROPIC_API_KEY` (local: `.env`; deploy: `st.secrets`).
- Ao terminar uma etapa: rodar os testes, marcar o checkbox no `ROTEIRO.md` e sugerir a mensagem de commit.
