"""Avaliação do agente: perguntas de referência e correção automática das respostas.

O valor esperado de cada pergunta é calculado no banco (SQL ou tool), nunca escrito à
mão. A correção procura esses valores no texto da resposta do agente.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.tools import FUNCOES, consultar_sql

CAMINHO_PERGUNTAS = Path(__file__).resolve().parent.parent / "tests" / "perguntas_teste.yaml"

# Frases que indicam que o agente reconheceu não ter o dado (perguntas do tipo "recusa")
RECUSA = re.compile(
    r"n[aã]o (h[aá]|tem|temos|possu|cobre|cont[eé]m|inclu|registr|abrang|consigo|[eé] poss[ií]vel|existe"
    r"|est[aã]o? dispon)"
    r"|apenas|somente|exclusivamente|fora d[oa]|sem dados|sem registros",
    re.IGNORECASE,
)
NUMERO = re.compile(r"\d[\d.,]*\d|\d")


@dataclass
class Pergunta:
    id: str
    categoria: str
    pergunta: str
    tipo: str = "valores"  # "valores" ou "recusa"
    sql: str | None = None
    ferramenta: dict[str, Any] | None = None
    tolerancia: float = 0.0
    aceitar: list[str] = field(default_factory=list)
    deve_conter: list[str] = field(default_factory=list)


def carregar_perguntas(caminho: Path = CAMINHO_PERGUNTAS) -> list[Pergunta]:
    return [Pergunta(**item) for item in yaml.safe_load(caminho.read_text(encoding="utf-8"))]


def valores_esperados(pergunta: Pergunta) -> list[Any]:
    """Valores que precisam aparecer na resposta, calculados agora no banco."""
    if pergunta.sql:
        r = consultar_sql(pergunta.sql)
        if r["erro"] or not r["linhas"]:
            raise ValueError(f"SQL de referência de '{pergunta.id}' falhou: {r['erro'] or 'sem linhas'}")
        return list(r["linhas"][0])
    if pergunta.ferramenta:
        f = pergunta.ferramenta
        saida = FUNCOES[f["nome"]](**f["args"])
        return [round(saida[f["campo"]] * f.get("escala", 1), 1)]
    return []


# ---------------------------------------------------------------- correção


def numeros_no_texto(texto: str) -> set[float]:
    """Todos os números do texto, lidos no formato brasileiro e no americano."""
    numeros: set[float] = set()
    for token in NUMERO.findall(texto):
        brasileiro = token.replace(".", "").replace(",", ".")
        americano = token.replace(",", "")
        for candidato in (brasileiro, americano):
            try:
                numeros.add(float(candidato))
            except ValueError:
                pass
    return numeros


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar nomes."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def contem_valor(texto: str, valor: Any, tolerancia: float) -> bool:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return any(abs(n - float(valor)) <= tolerancia + 1e-9 for n in numeros_no_texto(texto))
    return normalizar(str(valor)) in normalizar(texto)


def corrigir(pergunta: Pergunta, resposta: str, esperados: list[Any]) -> tuple[bool, str]:
    """Devolve (acertou, motivo) comparando a resposta com os valores esperados."""
    if pergunta.tipo == "recusa":
        faltando = [t for t in pergunta.deve_conter if normalizar(t) not in normalizar(resposta)]
        if not RECUSA.search(resposta):
            return False, "não disse que o dado está fora da base"
        if faltando:
            return False, f"faltou mencionar: {', '.join(faltando)}"
        return True, "reconheceu que o dado está fora da base"

    alternativas = [a for a in pergunta.aceitar if normalizar(a) in normalizar(resposta)]
    if alternativas:
        return True, f"aceito por citar: {', '.join(alternativas)}"
    ausentes = [v for v in esperados if not contem_valor(resposta, v, pergunta.tolerancia)]
    if ausentes:
        return False, f"não encontrou: {', '.join(str(v) for v in ausentes)}"
    return True, "valores conferem"
