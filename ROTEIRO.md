# 🎾 Scout de Tênis IA: roteiro de desenvolvimento

Agente que responde perguntas sobre tênis em linguagem natural, consultando dados reais da ATP com SQL e devolvendo números, tabelas e gráficos.

**Prazo:** 2 semanas (14 sessões de ~1–2h)
**Stack:** Python 3.11+, DuckDB, Claude API (tool use), Streamlit, Plotly
**Dados:** [Jeff Sackmann / tennis_atp](https://github.com/JeffSackmann/tennis_atp) (licença CC BY-NC-SA 4.0, cite no README)

---

## Como usar este roteiro no Claude Code

1. Crie a pasta do projeto e coloque este `ROTEIRO.md` e o `CLAUDE.md` nela.
2. Abra o Claude Code na pasta (`claude`).
3. Em cada etapa, copie o **prompt** para o Claude Code. Revise o que ele fizer antes de aceitar.
4. Ao final de cada etapa, rode o **teste de pronto** e faça um commit: `git commit -m "etapa X: ..."`.
5. Marque o checkbox `[x]` aqui no roteiro para acompanhar o progresso.

> Dica: comece cada sessão com *"Leia o ROTEIRO.md e o CLAUDE.md. Estamos na etapa X."* para o Claude retomar o contexto.

---

## Estrutura final esperada

```
scout-tenis-ia/
├── CLAUDE.md
├── ROTEIRO.md
├── README.md
├── requirements.txt
├── .env.example            # ANTHROPIC_API_KEY=...
├── .gitignore              # .env, data/, *.duckdb
├── data/                   # CSVs baixados (fora do git)
├── scripts/
│   └── carregar_dados.py   # baixa CSVs e monta o tenis.duckdb
├── src/
│   ├── db.py               # conexão e helpers do DuckDB
│   ├── tools.py            # funções que o agente pode chamar
│   ├── agente.py           # loop do agente com a Claude API
│   └── prompts.py          # prompt de sistema e glossário
├── app.py                  # interface Streamlit
└── tests/
    ├── test_tools.py
    └── perguntas_teste.yaml  # perguntas + respostas esperadas
```

---

## SEMANA 1: dados e agente

### Etapa 0: setup do projeto (dia 1)

- [ ] Repositório criado no GitHub
- [x] Ambiente virtual e dependências
- [ ] Chave da API em `.env`

**Prompt:**
```
Crie a estrutura de pastas descrita no ROTEIRO.md. Gere requirements.txt com:
duckdb, pandas, anthropic, streamlit, plotly, python-dotenv, requests, pytest, pyyaml.
Crie .gitignore (incluindo .env, data/, *.duckdb, .venv/) e .env.example.
Inicialize o git e faça o primeiro commit.
```

**Teste de pronto:** `pip install -r requirements.txt` roda sem erro e `git log` mostra o commit.

---

### Etapa 1: carga dos dados (dias 1–2)

- [x] Script baixa os CSVs de partidas 2000–atual, jogadores e rankings
- [x] Banco `tenis.duckdb` com tabelas limpas

> Nota: o repositório original `JeffSackmann/tennis_atp` saiu do GitHub. O script usa o fork
> `Kadantte/tennis_atp` (mesmos commits do autor, dados até jun/2026), configurável via `TENNIS_ATP_URL`.

Arquivos de origem (raw do GitHub):
- `atp_matches_{ano}.csv`: partidas (vencedor, perdedor, placar, superfície, estatísticas de saque)
- `atp_players.csv`: jogadores (id, nome, mão, nascimento, país, altura)
- `atp_rankings_10s.csv`, `atp_rankings_20s.csv`, `atp_rankings_current.csv`: rankings semanais

**Prompt:**
```
Escreva scripts/carregar_dados.py que:
1. Baixa de https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/
   os arquivos atp_matches_2000.csv até o ano atual (ignore 404 do ano corrente
   se ainda não existir), atp_players.csv e os rankings 10s, 20s e current.
   Salve em data/ e não baixe de novo se o arquivo já existir (flag --forcar para rebaixar).
2. Cria tenis.duckdb com as tabelas:
   - jogadores(player_id, nome_completo, mao, data_nascimento DATE, pais, altura_cm)
   - partidas: todas as colunas originais + tourney_date convertida para DATE
     + coluna ano
   - rankings(data_ranking DATE, posicao, player_id, pontos)
3. Cria uma VIEW partidas_jogador com uma linha por jogador por partida
   (colunas: player_id, adversario_id, venceu BOOL, superficie, data, torneio,
   rodada, placar, aces, duplas_faltas, pct_primeiro_saque, bp_salvos, bp_enfrentados...)
   Isso facilita muito as consultas do agente.
4. Imprime um resumo: nº de partidas, jogadores, intervalo de datas.
Use DuckDB lendo os CSVs direto (read_csv_auto) para ser rápido.
```

**Teste de pronto:**
```sql
-- no python: duckdb.connect("tenis.duckdb").sql("...").show()
SELECT COUNT(*) FROM partidas;                         -- > 60.000
SELECT * FROM partidas_jogador WHERE player_id = 104925 LIMIT 5;  -- Djokovic
```

---

### Etapa 2: tools do agente (dias 3–4)

- [x] `listar_tabelas()`: retorna esquema (tabelas, colunas, tipos)
- [x] `buscar_jogador(nome)`: busca aproximada → lista de (id, nome, país)
- [x] `consultar_sql(sql)`: executa só SELECT, limita a 200 linhas, timeout
- [x] `gerar_grafico(dados, tipo, x, y, titulo)`: devolve figura Plotly
- [x] Testes unitários

**Prompt:**
```
Implemente src/db.py (conexão read-only com tenis.duckdb, cacheada) e src/tools.py com:
- listar_tabelas() -> str com esquema de todas as tabelas e views
- buscar_jogador(nome: str) -> list[dict]: busca sem acento e case-insensitive,
  usando jaro_winkler_similarity do DuckDB, top 5
- consultar_sql(sql: str) -> dict {colunas, linhas, n_linhas, erro}:
  rejeite qualquer comando que não seja SELECT/WITH, aplique LIMIT 200 se não houver,
  e capture exceções devolvendo a mensagem de erro (o agente vai usá-la para se corrigir)
- gerar_grafico(dados, tipo: "barra"|"linha"|"dispersao"|"radar", x, y, titulo) -> dict
  com a figura Plotly serializada em JSON
Defina também TOOLS_SCHEMA: a lista de definições de tools no formato da Anthropic API
(name, description, input_schema), com descrições claras em português.
Escreva tests/test_tools.py cobrindo: busca "joao fonseca", SQL inválido,
tentativa de DROP bloqueada.
```

**Teste de pronto:** `pytest tests/test_tools.py` passa.

---

### Etapa 3: o agente (dias 5–7)

- [x] Prompt de sistema com esquema, glossário e regras
- [x] Loop de tool use (chama tools até ter a resposta final)
- [x] Autocorreção quando o SQL falha
- [ ] Teste no terminal

**Prompt (parte 1, prompts.py):**
```
Crie src/prompts.py com o SYSTEM_PROMPT do agente "Scout de Tênis IA":
- Papel: analista de tênis que responde em português, com dados, de forma objetiva.
- Regras: sempre usar buscar_jogador antes de filtrar por jogador; nunca inventar
  números; se a consulta falhar, ler o erro e corrigir; informar o período dos dados;
  sugerir gráfico quando houver comparação ou série temporal.
- Glossário: superfícies (Hard, Clay=saibro, Grass=grama, Carpet),
  tourney_level (G=Grand Slam, M=Masters 1000, A=ATP 250/500, F=Finals, D=Davis Cup),
  rodadas (R128...F), colunas de estatística (w_ace, w_1stIn, w_bpSaved etc.).
- 3 exemplos de pergunta → SQL correto (few-shot), ex.: H2H entre dois jogadores
  por superfície; % de vitórias no saibro desde 2020; top 10 em aces num ano.
O esquema das tabelas deve ser injetado dinamicamente via listar_tabelas().
```

**Prompt (parte 2, agente.py):**
```
Crie src/agente.py com a classe AgenteTenis:
- usa anthropic.Anthropic(), modelo lido de variável de ambiente ANTHROPIC_MODEL
  (com um default de modelo Sonnet atual)
- método perguntar(pergunta, historico) que roda o loop de tool use:
  envia mensagens + TOOLS_SCHEMA, executa cada tool_use pedido, devolve tool_result,
  repete até stop_reason == "end_turn" (máximo 8 iterações)
- retorna dict {resposta_texto, sqls_executados, graficos, n_iteracoes}
- registra log simples de cada passo (útil para mostrar o "raciocínio" na interface)
Adicione um bloco if __name__ == "__main__" para conversar pelo terminal.
```

**Teste de pronto:** no terminal, `python -m src.agente`, e o agente responde corretamente:
- "Qual o H2H entre Sinner e Alcaraz?"
- "Quem mais venceu Grand Slams desde 2000?"
- "Quantos aces o Isner fez em 2015?"

---

## SEMANA 2: interface, qualidade e publicação

### Etapa 4: interface Streamlit (dias 8–9)

- [x] Chat com histórico (`st.chat_message`)
- [x] Gráficos Plotly renderizados na resposta
- [x] Expander "🔍 Como cheguei nisso" com SQLs e passos
- [x] Sidebar com perguntas de exemplo clicáveis e período dos dados
- [x] Modo demonstração sem chave da API (`src/demo.py`): as 6 perguntas de exemplo rodam SQL pronto no banco

> Nota: sem `ANTHROPIC_API_KEY`, o app abre em modo demonstração. Com a chave, usa o agente
> de verdade. O teste de pronto foi feito no modo demonstração; falta repetir com a chave.

**Prompt:**
```
Crie app.py em Streamlit:
- título "🎾 Scout de Tênis IA" e subtítulo explicando a fonte dos dados
- chat com st.chat_input / st.chat_message, histórico em st.session_state
- para cada resposta: texto, gráficos (st.plotly_chart) e um st.expander
  "Como cheguei nisso" mostrando cada SQL executado (st.code, language="sql")
- sidebar: 6 perguntas de exemplo como botões, info do período dos dados,
  link para o GitHub, botão "limpar conversa"
- spinner enquanto o agente pensa; tratamento de erro amigável
- cache do agente com st.cache_resource
Use cores neutras e layout wide.
```

**Teste de pronto:** `streamlit run app.py` abre, as perguntas de exemplo funcionam e os gráficos aparecem.

---

### Etapa 5: qualidade e avaliação (dias 10–11)

- [ ] 10–15 perguntas de teste com resposta esperada
- [ ] Script de avaliação que mede a taxa de acerto
- [ ] Ajustes no prompt até atingir ≥ 80%

**Prompt:**
```
Crie tests/perguntas_teste.yaml com 12 perguntas variadas (H2H, ranking,
estatística de saque, recordes por superfície, evolução no tempo, pergunta
ambígua, pergunta fora do escopo dos dados) e, para cada uma, a resposta
esperada calculada via SQL direto no banco (gere esse SQL e rode para obter
o valor verdadeiro).
Depois crie scripts/avaliar.py que roda o agente em cada pergunta, compara
o número-chave da resposta com o esperado e imprime uma tabela com acertos,
nº de iterações e tempo. Salve o resultado em avaliacao.md.
```

**Teste de pronto:** `python scripts/avaliar.py` mostra taxa de acerto ≥ 80%. Esse número vai no README.

---

### Etapa 6: diferencial (dia 12, escolha um)

- [ ] **A) Cartão H2H:** tool `comparar_jogadores(a, b)` com radar por superfície e estatísticas de saque
- [x] **B) Elo por superfície:** calcular rating Elo histórico e tool `prever_partida(a, b, superficie)`

> Feito em `src/elo.py` + `scripts/calcular_elo.py` (roda junto com `carregar_dados.py`). A previsão usa
> a média do Elo geral com o da superfície. A validação desde 2023 (10.329 partidas) comparou K fixo e
> K dinâmico: o melhor foi K = 32 combinado, com 64,2% de acerto e Brier 0,219 (ranking ATP: 63,9%).
- [x] **C) Evolução no ranking:** gráfico de linha do ranking de 1+ jogadores ao longo do tempo (feito com o Elo de fim de ano; o agente também consegue com a tabela rankings)

**Prompt (exemplo B):**
```
Adicione em scripts/ um cálculo de Elo por superfície (K=32, rating inicial 1500)
percorrendo as partidas em ordem cronológica; salve a tabela elo(player_id,
superficie, data, rating) no DuckDB. Crie a tool prever_partida(jogador_a,
jogador_b, superficie) que retorna o Elo atual de cada um e a probabilidade de
vitória. Registre a tool no TOOLS_SCHEMA e atualize o prompt de sistema.
```

---

### Etapa 7: publicação (dias 13–14)

- [ ] README completo
- [ ] GIF de demonstração (ScreenToGif ou similar)
- [ ] Deploy no Streamlit Community Cloud
- [ ] Post no LinkedIn

**Prompt:**
```
Escreva um README.md profissional em português (com seção em inglês resumida):
- banner/título, GIF de demo (placeholder), link do app publicado
- problema e solução em 3 linhas
- arquitetura (diagrama mermaid: usuário → Streamlit → agente Claude → tools → DuckDB)
- stack, como rodar localmente, estrutura do projeto
- resultados da avaliação (taxa de acerto)
- próximos passos
- créditos e licença dos dados (Jeff Sackmann, CC BY-NC-SA 4.0)
Ajuste também o projeto para o deploy no Streamlit Cloud: o banco deve ser
gerado na primeira execução se não existir (ou use um subconjunto menor
de anos), e a chave da API deve vir de st.secrets.
```

**Deploy:** share.streamlit.io → conectar o repositório → `app.py` → em *Secrets*, adicionar `ANTHROPIC_API_KEY`.

**Post no LinkedIn (estrutura):** o problema → o que você construiu → GIF → 3 aprendizados técnicos → link do app e do GitHub.

---

## Checklist final do portfólio

- [ ] App publicado e funcionando
- [ ] README com GIF, arquitetura e métricas
- [ ] Código organizado, com testes passando
- [ ] Commits frequentes com mensagens claras
- [ ] Post publicado e projeto fixado no perfil do GitHub
