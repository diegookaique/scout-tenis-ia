# Avaliação do agente

**13 de 13 perguntas certas (100%)**: ✅ meta atingida de 80%.

IA: Gemini API (Google), gemini-flash-lite-latest · 30/10/2026 13:17 · gerado por `python scripts/avaliar.py`.
O valor esperado de cada pergunta é calculado no banco na hora da avaliação (SQL de referência em `tests/perguntas_teste.yaml`).

| # | Categoria | Pergunta | Esperado | Resultado | Iterações | SQL com erro | Tempo |
|---|---|---|---|---|---|---|---|
| 1 | Confronto direto | Quantas vezes o Djokovic venceu o Nadal? | 31 | ✅ valores conferem | 4 | 0 | 6 s |
| 2 | Títulos | Quantos Grand Slams o Nadal ganhou? | 22 | ✅ valores conferem | 3 | 0 | 4 s |
| 3 | Recorde por superfície | Quem tem mais vitórias no saibro desde 2000? | Nadal, 488 | ✅ valores conferem | 2 | 0 | 9 s |
| 4 | Estatística de saque | Qual o percentual de pontos ganhos com o primeiro saque do Federer em 2017? | 79.8 | ✅ valores conferem | 3 | 0 | 9 s |
| 5 | Evolução no tempo | Em que ano o Djokovic teve o maior percentual de vitórias? | 2015 | ✅ valores conferem | 3 | 0 | 6 s |
| 6 | Ranking | Quem era o número 1 do ranking no início de 2020? | Nadal | ✅ valores conferem | 2 | 0 | 4 s |
| 7 | Ranking | Em quantas semanas o Federer foi número 1 do ranking, nos dados disponíveis? | 44 | ✅ valores conferem | 4 | 0 | 9 s |
| 8 | Comparação | Quem fez mais aces em 2024, Hurkacz ou Zverev? | Hurkacz, 843 | ✅ valores conferem | 4 | 0 | 7 s |
| 9 | Jogador brasileiro | Quantas partidas o João Fonseca venceu em 2025? | 27 | ✅ valores conferem | 3 | 0 | 6 s |
| 10 | Previsão (Elo) | Qual a chance do Alcaraz vencer o Zverev no saibro? | 71.2 | ✅ valores conferem | 3 | 0 | 18 s |
| 11 | Pergunta ambígua | Quantas partidas o Zverev venceu em 2017? | 57 | ✅ valores conferem | 3 | 0 | 4 s |
| 12 | Fora do escopo | Quem é a número 1 do ranking da WTA? | dizer que não há o dado | ✅ reconheceu que o dado está fora da base | 1 | 0 | 11 s |
| 13 | Fora do período | Quantos títulos o Guga Kuerten ganhou em 1997? | dizer que não há o dado | ✅ reconheceu que o dado está fora da base | 5 | 0 | 6 s |

## Respostas do agente

<details><summary>✅ 1. Quantas vezes o Djokovic venceu o Nadal?</summary>

> Novak Djokovic venceu Rafael Nadal **31 vezes** em partidas oficiais do circuito ATP (no período cobbido de 2000 a 2026).
> 
> Por superfície, o histórico de vitórias de Djokovic sobre Nadal é o seguinte:
> - **Quadra dura (Hard):** 20 vitórias
> - **Saibro (Clay):** 9 vitórias
> - **Grama (Grass):** 2 vitórias
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 2. Quantos Grand Slams o Nadal ganhou?</summary>

> O Rafael Nadal ganhou **22** Grand Slams no circuito principal entre 2000 e 2025 nos dados disponíveis.
> 
> *Fonte: dados de Jeff Sackmann (tennis_atp).*

</details>

<details><summary>✅ 3. Quem tem mais vitórias no saibro desde 2000?</summary>

> **Rafael Nadal** tem o maior número de vitórias no saibro desde 2000, com **488** partidas vencidas.
> 
> Contexto adicional: os dados cobrem o período de 03/01/2000 a 25/05/2026.
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 4. Qual o percentual de pontos ganhos com o primeiro saque do Federer em 2017?</summary>

> O percentual de pontos ganhos com o primeiro saque de Roger Federer em 2017 foi de **79,78%** (2.182 pontos ganhos em 2.735 primeiros saques válidos).
> 
> Contexto: Em 2017, Federer disputou partidas do circuito principal em que as estatísticas de saque estavam registradas, conquistando títulos importantes como o Australian Open e Wimbledon naquela temporada.
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 5. Em que ano o Djokovic teve o maior percentual de vitórias?</summary>

> O ano em que Novak Djokovic teve o maior percentual de vitórias foi **2015**, com **93,26%** de aproveitamento (83 vitórias em 89 partidas). 
> 
> Principais anos com maior aproveitamento (considerando anos com pelo menos 10 partidas disputadas):
> 1. **2015**: 93,26% (83V - 6D)
> 2. **2011**: 91,14% (72V - 7D)
> 3. **2013**: 89,16% (74V - 9D)
> 4. **2020**: 89,13% (41V - 5D)
> 5. **2014**: 89,04% (65V - 8D)
> 
> *Dados de Jeff Sackmann (tennis_atp).*

</details>

<details><summary>✅ 6. Quem era o número 1 do ranking no início de 2020?</summary>

> Rafael Nadal era o número 1 do ranking da ATP no início de 2020 (em 6 de janeiro de 2020), com 9.985 pontos.
> 
> *Dados de Jeff Sackmann (tennis_atp).*

</details>

<details><summary>✅ 7. Em quantas semanas o Federer foi número 1 do ranking, nos dados disponíveis?</summary>

> O Roger Federer foi número 1 do ranking durante **44 semanas** nos dados disponíveis.
> 
> Vale destacar que os dados semanais de ranking da base começam em **4 de janeiro de 2010**, período em que o Federer já estava na reta final de suas semanas acumuladas no topo do ranking (o grosso de suas 310 semanas como número 1 da carreira ocorreu antes de 2010).
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 8. Quem fez mais aces em 2024, Hurkacz ou Zverev?</summary>

> **Hubert Hurkacz** fez mais aces em 2024.
> 
> * **Hubert Hurkacz:** 843 aces (em 64 partidas com estatísticas registradas)
> * **Alexander Zverev:** 837 aces (em 90 partidas com estatísticas registradas)
> 
> Apesar de ter disputado menos partidas ao longo do ano, Hurkacz superou Zverev por uma margem de 6 aces.
> 
> Fontes: Dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 9. Quantas partidas o João Fonseca venceu em 2025?</summary>

> O João Fonseca venceu **27** partidas em 2025 no circuito principal da ATP.
> 
> *Dados de Jeff Sackmann (tennis_atp).*

</details>

<details><summary>✅ 10. Qual a chance do Alcaraz vencer o Zverev no saibro?</summary>

> De acordo com o modelo de rating Elo, a probabilidade de **Carlos Alcaraz** vencer **Alexander Zverev** no saibro é de **71,2%** (contra 28,8% para Zverev).
> 
> **Contexto dos jogadores no saibro:**
> * **Carlos Alcaraz:** Elo no saibro de 2071 (128 partidas registradas na superfície até abril de 2026).
> * **Alexander Zverev:** Elo no saibro de 1930 (255 partidas registradas na superfície até maio de 2026).
> 
> *Nota: Esta é uma estimativa estatística baseada no histórico de ratings Elo (que combina o rating geral com o específico da superfície), e não considera lesões recentes ou fatores momentâneos. O modelo acerta o vencedor em cerca de 64% das partidas desde 2023.*
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 11. Quantas partidas o Zverev venceu em 2017?</summary>

> Alexander Zverev venceu **57** partidas no circuito ATP em 2017.
> 
> Dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 12. Quem é a número 1 do ranking da WTA?</summary>

> O banco de dados do circuito de tênis cobre exclusivamente o circuito masculino (ATP), de modo que não há informações sobre o ranking da WTA (circuito feminino).
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 13. Quantos títulos o Guga Kuerten ganhou em 1997?</summary>

> Gustavo Kuerten não possui registros de títulos em 1997 na base de dados, pois o período coberto por estes dados inicia-se em **2000** (portanto, conquistas anteriores como Roland Garros de 1997 não estão incluídas).
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

