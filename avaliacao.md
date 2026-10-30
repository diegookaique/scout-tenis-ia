# Avaliação do agente

**13 de 13 perguntas certas (100%)**: ✅ meta atingida de 80%.

IA: Gemini API (Google), gemini-flash-lite-latest · 30/10/2026 14:31 · gerado por `python scripts/avaliar.py`.
O valor esperado de cada pergunta é calculado no banco na hora da avaliação (SQL de referência em `tests/perguntas_teste.yaml`).

| # | Categoria | Pergunta | Esperado | Resultado | Iterações | SQL com erro | Tempo |
|---|---|---|---|---|---|---|---|
| 1 | Confronto direto | Quantas vezes o Djokovic venceu o Nadal? | 31 | ✅ valores conferem | 3 | 0 | 4 s |
| 2 | Títulos | Quantos Grand Slams o Nadal ganhou? | 22 | ✅ valores conferem | 4 | 0 | 5 s |
| 3 | Recorde por superfície | Quem tem mais vitórias no saibro desde 2000? | Nadal, 488 | ✅ valores conferem | 2 | 0 | 2 s |
| 4 | Estatística de saque | Qual o percentual de pontos ganhos com o primeiro saque do Federer em 2017? | 79.8 | ✅ valores conferem | 3 | 0 | 7 s |
| 5 | Evolução no tempo | Em que ano o Djokovic teve o maior percentual de vitórias? | 2015 | ✅ valores conferem | 4 | 0 | 6 s |
| 6 | Ranking | Quem era o número 1 do ranking no início de 2020? | Nadal | ✅ valores conferem | 2 | 0 | 2 s |
| 7 | Ranking | Em quantas semanas o Federer foi número 1 do ranking, nos dados disponíveis? | 44 | ✅ valores conferem | 3 | 0 | 3 s |
| 8 | Comparação | Quem fez mais aces em 2024, Hurkacz ou Zverev? | Hurkacz, 843 | ✅ valores conferem | 4 | 0 | 40 s |
| 9 | Jogador brasileiro | Quantas partidas o João Fonseca venceu em 2025? | 27 | ✅ valores conferem | 3 | 0 | 4 s |
| 10 | Previsão (Elo) | Qual a chance do Alcaraz vencer o Zverev no saibro? | 71.2 | ✅ valores conferem | 3 | 0 | 4 s |
| 11 | Pergunta ambígua | Quantas partidas o Zverev venceu em 2017? | 57 | ✅ valores conferem | 3 | 0 | 3 s |
| 12 | Fora do escopo | Quem é a número 1 do ranking da WTA? | dizer que não há o dado | ✅ reconheceu que o dado está fora da base | 1 | 0 | 1 s |
| 13 | Fora do período | Quantos títulos o Guga Kuerten ganhou em 1997? | dizer que não há o dado | ✅ reconheceu que o dado está fora da base | 5 | 1 | 10 s |

## Respostas do agente

<details><summary>✅ 1. Quantas vezes o Djokovic venceu o Nadal?</summary>

> Novak Djokovic venceu Rafael Nadal **31** vezes no circuito principal (período de 2000 a 25/05/2026).
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 2. Quantos Grand Slams o Nadal ganhou?</summary>

> Rafael Nadal ganhou **22** títulos de Grand Slam no circuito ATP (desde 2000, período coberto pelos dados):
> 
> * **Roland Garros:** 14
> * **US Open:** 4
> * **Wimbledon:** 2
> * **Australian Open:** 2
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 3. Quem tem mais vitórias no saibro desde 2000?</summary>

> **Rafael Nadal** é o jogador com mais vitórias no saibro desde 2000, somando **488 vitórias** no período.
> 
> Aqui está o top 5 de jogadores com mais vitórias no saibro no circuito ATP desde 2000:
> 
> 1. **Rafael Nadal**: 488 vitórias
> 2. **David Ferrer**: 337 vitórias
> 3. **Novak Djokovic**: 302 vitórias
> 4. **Nicolas Almagro**: 281 vitórias
> 5. **Tommy Robredo**: 259 vitórias
> 
> *Fonte: Dados de Jeff Sackmann (tennis_atp), cobrindo o período de 03/01/2000 a 25/05/2026.*

</details>

<details><summary>✅ 4. Qual o percentual de pontos ganhos com o primeiro saque do Federer em 2017?</summary>

> O percentual de pontos ganhos com o primeiro saque do Roger Federer em 2017 foi de **79,8%** (2.182 pontos ganhos em 2.735 primeiros saques dentro).
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 5. Em que ano o Djokovic teve o maior percentual de vitórias?</summary>

> O Novak Djokovic teve o seu maior percentual de vitórias em **2015**, quando obteve **93,26%** de aproveitamento (83 vitórias e 6 derrotas em 89 partidas).
> 
> ### Principais temporadas de Novak Djokovic (mínimo de 10 partidas no ano):
> 
> 1. **2015**: 83 vitórias / 6 derrotas (**93,26%**)
> 2. **2011**: 72 vitórias / 7 derrotas (**91,14%**)
> 3. **2013**: 74 vitórias / 9 derrotas (**89,16%**)
> 4. **2020**: 41 vitórias / 5 derrotas (**89,13%**)
> 5. **2014**: 65 vitórias / 8 derrotas (**89,04%**)
> 
> *Dados de Jeff Sackmann (tennis_atp), cobrindo o período de 2000 a 25/05/2026.*

</details>

<details><summary>✅ 6. Quem era o número 1 do ranking no início de 2020?</summary>

> O número 1 do ranking no início de 2020 era **Rafael Nadal**, com 9.985 pontos, conforme a atualização oficial do ranking em **6 de janeiro de 2020**.
> 
> Dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 7. Em quantas semanas o Federer foi número 1 do ranking, nos dados disponíveis?</summary>

> O Roger Federer foi número 1 do ranking mundial durante **44 semanas** nos dados disponíveis (período de 04/01/2010 a 18/06/2018, dentro da cobertura de rankings semanais que se inicia em 2010).
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 8. Quem fez mais aces em 2024, Hurkacz ou Zverev?</summary>

> **Hubert Hurkacz** fez mais aces em 2024, com **843 aces** (em 64 partidas com estatísticas registradas), contra **837 aces** de Alexander Zverev (em 90 partidas).
> 
> Dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 9. Quantas partidas o João Fonseca venceu em 2025?</summary>

> O João Fonseca venceu **27** partidas no circuito ATP em 2025.
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 10. Qual a chance do Alcaraz vencer o Zverev no saibro?</summary>

> Segundo o modelo de rating Elo para partidas no saibro (Clay), a chance de vitória de **Carlos Alcaraz** sobre **Alexander Zverev** é de **71,2%** contra **28,8%** de Zverev. 
> 
> **Detalhes dos ratings atuais:**
> * **Carlos Alcaraz:** Elo Geral de 2204 | Elo no Saibro de 2071 (Combinado: 2138)
> * **Alexander Zverev:** Elo Geral de 2032 | Elo no Saibro de 1930 (Combinado: 1981)
> 
> *Aviso: O cálculo é uma estimativa baseada no histórico de ratings Elo (que considera o nível geral e específico na superfície, sem incluir fatores como lesões recentes ou o histórico de confrontos diretos entre eles). O modelo tem taxa histórica de acerto de cerca de 64% desde 2023.*
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 11. Quantas partidas o Zverev venceu em 2017?</summary>

> Alexander Zverev venceu **57** partidas em 2017.
> 
> Neste ano, o tenista alemão conquistou 5 títulos no circuito ATP (incluindo dois Masters 1000, em Roma e Montreal) e terminou a temporada no top 5 do ranking mundial.
> 
> Dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 12. Quem é a número 1 do ranking da WTA?</summary>

> Os dados do banco cobrem exclusivamente o circuito profissional masculino (ATP). Não há informações sobre o ranking ou torneios da WTA (circuito feminino).
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

<details><summary>✅ 13. Quantos títulos o Guga Kuerten ganhou em 1997?</summary>

> Os dados do circuito cobrem o período a partir de **2000** (até 25/05/2026), portanto não registram as partidas e títulos de Gustavo Kuerten (Guga) em 1997 — incluindo sua histórica conquista de Roland Garros naquele ano.
> 
> Fonte: dados de Jeff Sackmann (tennis_atp).

</details>

