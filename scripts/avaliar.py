"""Avalia o agente nas perguntas de referência e salva o resultado em avaliacao.md.

Uso (da raiz do projeto, com GEMINI_API_KEY ou ANTHROPIC_API_KEY no .env):
    python scripts/avaliar.py
    python scripts/avaliar.py --ids h2h saque      # só algumas perguntas
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.avaliacao import Pergunta, carregar_perguntas, corrigir, valores_esperados  # noqa: E402
from src.provedores import NOMES, chaves_do_ambiente, criar_agente, descrever_erro, escolher_provedor  # noqa: E402

CAMINHO_SAIDA = RAIZ / "avaliacao.md"
META = 0.8
TENTATIVAS = 3  # a mesma pergunta é refeita se a API estiver sobrecarregada
ESPERA_FALHA = 30  # segundos antes de refazer


@dataclass
class Resultado:
    pergunta: Pergunta
    esperados: list[Any]
    acertou: bool
    motivo: str
    resposta: str
    iteracoes: int
    sqls_com_erro: int
    segundos: float


def perguntar_com_tentativas(agente: Any, texto: str) -> dict[str, Any]:
    """Chama o agente; em erro de API (ex.: sobrecarga do plano gratuito), espera e tenta de novo."""
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            return agente.perguntar(texto)
        except Exception as erro:
            mensagem = descrever_erro(erro)
            if mensagem is None or tentativa == TENTATIVAS:
                raise
            print(f"    ({mensagem} Nova tentativa em {ESPERA_FALHA} s.)")
            time.sleep(ESPERA_FALHA)
    raise AssertionError("inalcançável")


def avaliar(agente: Any, pergunta: Pergunta) -> Resultado:
    esperados = valores_esperados(pergunta)
    inicio = time.time()
    try:
        r = perguntar_com_tentativas(agente, pergunta.pergunta)
    except Exception as erro:
        motivo = descrever_erro(erro) or f"{type(erro).__name__}: {erro}"
        return Resultado(pergunta, esperados, False, f"erro: {motivo}", "", 0, 0, time.time() - inicio)
    acertou, motivo = corrigir(pergunta, r["resposta_texto"], esperados)
    sqls_com_erro = sum(1 for s in r["sqls_executados"] if s["erro"])
    return Resultado(pergunta, esperados, acertou, motivo, r["resposta_texto"], r["n_iteracoes"],
                     sqls_com_erro, time.time() - inicio)


# ---------------------------------------------------------------- relatório


def _esperado(r: Resultado) -> str:
    if r.pergunta.tipo == "recusa":
        return "dizer que não há o dado"
    return ", ".join(f"{v:g}" if isinstance(v, float) else str(v) for v in r.esperados)


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def montar_relatorio(resultados: list[Resultado], ia: str) -> str:
    acertos = sum(r.acertou for r in resultados)
    taxa = acertos / len(resultados)
    situacao = "✅ meta atingida" if taxa >= META else "❌ abaixo da meta"
    linhas = [
        "# Avaliação do agente",
        "",
        f"**{acertos} de {len(resultados)} perguntas certas ({taxa:.0%})**: {situacao} de {META:.0%}.",
        "",
        f"IA: {ia} · {datetime.now():%d/%m/%Y %H:%M} · gerado por `python scripts/avaliar.py`.",
        "O valor esperado de cada pergunta é calculado no banco na hora da avaliação "
        "(SQL de referência em `tests/perguntas_teste.yaml`).",
        "",
        "| # | Categoria | Pergunta | Esperado | Resultado | Iterações | SQL com erro | Tempo |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, r in enumerate(resultados, start=1):
        marca = "✅" if r.acertou else "❌"
        linhas.append(
            f"| {n} | {r.pergunta.categoria} | {_celula(r.pergunta.pergunta)} | {_celula(_esperado(r))} "
            f"| {marca} {_celula(r.motivo)} | {r.iteracoes} | {r.sqls_com_erro} | {r.segundos:.0f} s |"
        )
    linhas += ["", "## Respostas do agente", ""]
    for n, r in enumerate(resultados, start=1):
        marca = "✅" if r.acertou else "❌"
        linhas += [
            f"<details><summary>{marca} {n}. {r.pergunta.pergunta}</summary>", "",
            "\n".join(f"> {linha}" for linha in (r.resposta or "(sem resposta)").splitlines()), "",
            "</details>", "",
        ]
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- execução


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia o agente nas perguntas de referência.")
    parser.add_argument("--ids", nargs="*", help="ids das perguntas (padrão: todas)")
    parser.add_argument("--pausa", type=float, default=5, help="segundos entre perguntas (limite gratuito)")
    args = parser.parse_args()

    load_dotenv(RAIZ / ".env")
    provedor, chave = escolher_provedor(chaves_do_ambiente(), os.getenv("PROVEDOR", ""))
    if provedor == "demo":
        sys.exit("Nenhuma chave de IA configurada. Preencha GEMINI_API_KEY no .env.")
    agente = criar_agente(provedor, chave)
    ia = f"{NOMES[provedor]}, {agente.modelo}"

    perguntas = [p for p in carregar_perguntas() if not args.ids or p.id in args.ids]
    print(f"Avaliando {len(perguntas)} perguntas com {ia}...\n")
    resultados = []
    for n, pergunta in enumerate(perguntas, start=1):
        r = avaliar(agente, pergunta)
        resultados.append(r)
        print(f"{n:2}. {'✅' if r.acertou else '❌'} {pergunta.pergunta}  [{r.motivo}; {r.segundos:.0f} s]")
        if n < len(perguntas):
            time.sleep(args.pausa)

    relatorio = montar_relatorio(resultados, ia)
    if not args.ids:  # só a avaliação completa substitui o relatório
        CAMINHO_SAIDA.write_text(relatorio, encoding="utf-8")
        print(f"\nRelatório salvo em {CAMINHO_SAIDA.name}")
    print("\n" + relatorio.splitlines()[2])


if __name__ == "__main__":
    main()
