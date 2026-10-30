"""Rating Elo por superfície: cálculo, previsão e validação.

Cada jogador tem um Elo geral (todas as superfícies) e um Elo por superfície.
A previsão usa a média dos dois: o Elo da superfície sozinho tem poucas partidas
(principalmente na grama) e o geral ignora a especialidade do jogador.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
import random
from math import log

RATING_INICIAL = 1500.0
GERAL = "Geral"
SUPERFICIES = ("Hard", "Clay", "Grass", "Carpet")


def prob_vitoria(rating_a: float, rating_b: float) -> float:
    """Probabilidade de A vencer B pela fórmula logística do Elo (escala 400)."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def fator_k(partidas_disputadas: int, k_fixo: float | None = None) -> float:
    """Quanto o rating se move numa partida.

    Por padrão o K diminui com a experiência (fórmula usada pelo FiveThirtyEight
    para o tênis): estreantes se ajustam rápido e veteranos ficam estáveis.
    Com `k_fixo`, usa um K constante (o K=32 clássico).
    """
    if k_fixo is not None:
        return k_fixo
    return 250 / (partidas_disputadas + 5) ** 0.4


def combinar(elo_geral: float, elo_superficie: float) -> float:
    return (elo_geral + elo_superficie) / 2


@dataclass(frozen=True)
class Partida:
    data: date
    vencedor: int
    perdedor: int
    superficie: str


@dataclass(frozen=True)
class Atualizacao:
    """Ratings de um jogador depois de uma partida, numa das escalas (Geral ou superfície)."""

    player_id: int
    escala: str
    data: date
    rating: float
    partidas: int


@dataclass(frozen=True)
class Previsao:
    """Probabilidade que o modelo dava ao vencedor real, antes da partida."""

    data: date
    superficie: str
    prob_geral: float
    prob_superficie: float
    prob_combinada: float


class CalculadoraElo:
    """Percorre partidas em ordem cronológica mantendo os ratings de cada escala."""

    def __init__(self, k_fixo: float | None = None):
        self.k_fixo = k_fixo
        self.rating: dict[tuple[int, str], float] = defaultdict(lambda: RATING_INICIAL)
        self.partidas: dict[tuple[int, str], int] = defaultdict(int)

    def processar(self, partidas: Iterable[Partida]) -> Iterator[tuple[Previsao, list[Atualizacao]]]:
        """Para cada partida, devolve a previsão feita antes dela e os ratings depois dela."""
        for p in partidas:
            previsao = self._prever_vencedor(p)
            atualizacoes = self._atualizar(p, GERAL) + self._atualizar(p, p.superficie)
            yield previsao, atualizacoes

    def _prever_vencedor(self, p: Partida) -> Previsao:
        geral_v, geral_p = self.rating[(p.vencedor, GERAL)], self.rating[(p.perdedor, GERAL)]
        sup_v, sup_p = self.rating[(p.vencedor, p.superficie)], self.rating[(p.perdedor, p.superficie)]
        return Previsao(
            data=p.data,
            superficie=p.superficie,
            prob_geral=prob_vitoria(geral_v, geral_p),
            prob_superficie=prob_vitoria(sup_v, sup_p),
            prob_combinada=prob_vitoria(combinar(geral_v, sup_v), combinar(geral_p, sup_p)),
        )

    def _atualizar(self, p: Partida, escala: str) -> list[Atualizacao]:
        chave_v, chave_p = (p.vencedor, escala), (p.perdedor, escala)
        esperado = prob_vitoria(self.rating[chave_v], self.rating[chave_p])
        self.rating[chave_v] += fator_k(self.partidas[chave_v], self.k_fixo) * (1 - esperado)
        self.rating[chave_p] -= fator_k(self.partidas[chave_p], self.k_fixo) * (1 - esperado)
        self.partidas[chave_v] += 1
        self.partidas[chave_p] += 1
        return [
            Atualizacao(chave[0], escala, p.data, self.rating[chave], self.partidas[chave])
            for chave in (chave_v, chave_p)
        ]


def metricas(probs_do_vencedor: list[float]) -> dict[str, float]:
    """Acurácia (o favorito venceu), Brier score e log loss de um conjunto de previsões.

    Cada valor é a probabilidade que o modelo dava a quem de fato venceu.
    Empates em 50% contam como meio acerto.
    """
    n = len(probs_do_vencedor)
    acertos = sum(1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0 for p in probs_do_vencedor)
    brier = sum((1 - p) ** 2 for p in probs_do_vencedor) / n
    perda = -sum(log(max(p, 1e-12)) for p in probs_do_vencedor) / n
    return {"partidas": n, "acuracia": acertos / n, "brier": brier, "log_loss": perda}


# ---------------------------------------------------------------- simulação de torneio

FASES = ("semifinal", "final", "titulo")


def simular_torneio(ratings: list[float], simulacoes: int = 20_000, semente: int = 42) -> list[dict[str, float]]:
    """Monte Carlo de um torneio; `ratings` em ordem de cabeça de chave.

    Com 8 jogadores, usa o formato do ATP Finals: dois grupos de 4 em todos contra
    todos (1-4-5-8 e 2-3-6-7), os dois melhores de cada grupo nas semifinais cruzadas
    e a final. Com outra potência de 2, é mata-mata com o 1 e o 2 em lados opostos.
    Devolve, para cada jogador, a fração das simulações em que chegou à semifinal,
    à final e ao título. A semente fixa torna o resultado reproduzível.
    """
    n = len(ratings)
    if n < 4 or n > 32 or n & (n - 1):
        raise ValueError("O torneio precisa de 4, 8, 16 ou 32 jogadores.")
    rng = random.Random(semente)
    contagem = [dict.fromkeys(FASES, 0) for _ in ratings]

    def jogo(a: int, b: int) -> int:
        return a if rng.random() < prob_vitoria(ratings[a], ratings[b]) else b

    for _ in range(simulacoes):
        semifinalistas = _fase_de_grupos(jogo, rng) if n == 8 else _mata_mata_ate(jogo, _chave(n), 4)
        for j in semifinalistas:
            contagem[j]["semifinal"] += 1
        finalistas = [jogo(semifinalistas[0], semifinalistas[1]), jogo(semifinalistas[2], semifinalistas[3])]
        for j in finalistas:
            contagem[j]["final"] += 1
        contagem[jogo(*finalistas)]["titulo"] += 1
    return [{fase: c[fase] / simulacoes for fase in FASES} for c in contagem]


def _fase_de_grupos(jogo, rng: random.Random) -> list[int]:
    """Grupos do ATP Finals; devolve [1º A, 2º B, 1º B, 2º A] (semifinais cruzadas)."""
    classificados = []
    for grupo in ((0, 3, 4, 7), (1, 2, 5, 6)):
        vitorias = dict.fromkeys(grupo, 0)
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                vitorias[jogo(a, b)] += 1
        # Empate em vitórias: desempate aleatório (o real usa sets e games, que não simulamos)
        ordem = sorted(grupo, key=lambda j: (vitorias[j], rng.random()), reverse=True)
        classificados.append(ordem[:2])
    (a1, a2), (b1, b2) = classificados
    return [a1, b2, b1, a2]


def _chave(n: int) -> list[int]:
    """Ordem da chave com cabeças de chave: para 8, [0, 7, 3, 4, 1, 6, 2, 5]."""
    ordem = [0]
    while len(ordem) < n:
        tamanho = len(ordem) * 2
        ordem = [x for semente in ordem for x in (semente, tamanho - 1 - semente)]
    return ordem


def _mata_mata_ate(jogo, chave: list[int], restantes: int) -> list[int]:
    """Joga as rodadas da chave até sobrarem `restantes` jogadores, na ordem da chave."""
    while len(chave) > restantes:
        chave = [jogo(chave[i], chave[i + 1]) for i in range(0, len(chave), 2)]
    return chave
