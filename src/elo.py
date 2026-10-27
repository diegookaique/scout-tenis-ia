"""Rating Elo por superfície: cálculo, previsão e validação.

Cada jogador tem um Elo geral (todas as superfícies) e um Elo por superfície.
A previsão usa a média dos dois: o Elo da superfície sozinho tem poucas partidas
(principalmente na grama) e o geral ignora a especialidade do jogador.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
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
