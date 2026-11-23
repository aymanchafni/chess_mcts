"""Évaluation tactique sur les problèmes Lichess (échecs complets).

Base publique : https://database.lichess.org/#puzzles  (lichess_db_puzzle.csv.zst)
Colonnes : PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags

Format Lichess : la FEN est la position AVANT le coup de l'adversaire.
Moves = « coup adverse, solution 1, réponse adverse, solution 2, ... ».
Le problème est réussi si le joueur trouve chaque coup de la solution
(comme sur Lichess, tout coup qui donne mat est accepté).

Exemples :
    python -m minichess.puzzles --fichier donnees/puzzles_exemple.csv --joueurs alphabeta --budget 5000
    python -m minichess.puzzles --fichier lichess_db_puzzle.csv.zst --themes mateIn2 hangingPiece \\
        --elo-max 1600 --n 300 --joueurs alphabeta "uct:c=1.4" --budget 20000 --processus 4
"""

import argparse
import csv
import io
import random
from collections import defaultdict
from multiprocessing import Pool

import chess

from .echecs import JeuEchecs
from .joueurs import creer_joueur


def _ouvrir(chemin):
    if chemin.endswith(".zst"):
        import zstandard  # pip install zstandard
        flux = zstandard.ZstdDecompressor().stream_reader(open(chemin, "rb"))
        return io.TextIOWrapper(flux, encoding="utf-8")
    return open(chemin, encoding="utf-8")


COLONNES = ["PuzzleId", "FEN", "Moves", "Rating", "RatingDeviation", "Popularity",
            "NbPlays", "Themes", "GameUrl", "OpeningTags"]


def charger_puzzles(chemin, themes=None, elo_min=0, elo_max=10_000, n=None, graine=0, max_lus=None):
    """Lit le CSV et garde les problèmes qui ont AU MOINS un des thèmes demandés.
    Si n est donné, tire n problèmes au hasard (reproductible via `graine`)."""
    themes = set(themes or [])
    choisis = []
    with _ouvrir(chemin) as f:
        lecteur = csv.reader(f)
        for i, ligne in enumerate(lecteur):
            if max_lus and i >= max_lus:
                break
            if not ligne or ligne[0] == "PuzzleId":
                continue
            p = dict(zip(COLONNES, ligne))
            p["Rating"] = int(p["Rating"])
            p["Themes"] = p["Themes"].split()
            if not elo_min <= p["Rating"] <= elo_max:
                continue
            if themes and not themes.intersection(p["Themes"]):
                continue
            choisis.append(p)
    if n is not None and n < len(choisis):
        choisis = random.Random(graine).sample(choisis, n)
    return choisis


def resoudre(joueur, puzzle, budget):
    """True si le joueur trouve toute la solution."""
    board = chess.Board(puzzle["FEN"])
    coups = puzzle["Moves"].split()
    board.push_uci(coups[0])                      # coup de l'adversaire
    joueur.nouvelle_partie()
    for i in range(1, len(coups), 2):
        jeu = JeuEchecs(board.copy(stack=False))
        propose = joueur.choisir_coup(jeu, budget)
        if propose.uci() != coups[i]:
            essai = board.copy(stack=False)
            essai.push(propose)
            if not (i == len(coups) - 1 and essai.is_checkmate()):
                return False
        board.push_uci(coups[i])
        if i + 1 < len(coups):
            board.push_uci(coups[i + 1])          # réponse de l'adversaire
    return True


def _tache(args):
    spec, puzzle, budget = args
    return spec, puzzle["PuzzleId"], puzzle["Rating"], puzzle["Themes"], \
        resoudre(creer_joueur(spec), puzzle, budget)


def evaluer(joueurs, puzzles, budget, processus=1, themes_rapport=None):
    taches = [(j, p, budget) for j in joueurs for p in puzzles]
    if processus > 1:
        with Pool(processus) as pool:
            res = pool.map(_tache, taches)
    else:
        res = [_tache(t) for t in taches]

    # taux de réussite global et par thème
    par_theme = defaultdict(lambda: [0, 0])  # (joueur, thème) -> [réussis, total]
    for spec, _, _, themes, ok in res:
        for th in ["TOUS"] + [t for t in themes if not themes_rapport or t in themes_rapport]:
            par_theme[(spec, th)][0] += ok
            par_theme[(spec, th)][1] += 1
    return res, par_theme


def main():
    p = argparse.ArgumentParser(description="Taux de réussite sur des problèmes Lichess.")
    p.add_argument("--fichier", required=True)
    p.add_argument("--joueurs", nargs="+", required=True)
    p.add_argument("--themes", nargs="*", default=None, help="ex. mateIn1 mateIn2 hangingPiece fork")
    p.add_argument("--elo-min", type=int, default=0)
    p.add_argument("--elo-max", type=int, default=10_000)
    p.add_argument("--n", type=int, default=None)
    p.add_argument("--budget", type=int, default=5000)
    p.add_argument("--processus", type=int, default=1)
    p.add_argument("--graine", type=int, default=0)
    p.add_argument("--sortie", help="CSV détaillé (une ligne par joueur et problème)")
    a = p.parse_args()

    puzzles = charger_puzzles(a.fichier, a.themes, a.elo_min, a.elo_max, a.n, a.graine)
    print(f"{len(puzzles)} problèmes chargés.")
    res, par_theme = evaluer(a.joueurs, puzzles, a.budget, a.processus, set(a.themes or []))

    print(f"\n{'Joueur':<30} {'Thème':<18} {'Réussis':>12} {'Taux':>7}")
    print("-" * 70)
    for (spec, th), (ok, tot) in sorted(par_theme.items(), key=lambda kv: (kv[0][0], kv[0][1] != "TOUS", kv[0][1])):
        print(f"{spec:<30} {th:<18} {ok:>5} / {tot:<5} {ok / tot:>7.1%}")

    if a.sortie:
        with open(a.sortie, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["joueur", "puzzle_id", "rating", "themes", "reussi", "budget"])
            for spec, pid, rating, themes, ok in res:
                w.writerow([spec, pid, rating, " ".join(themes), int(ok), a.budget])
        print(f"\nRésultats détaillés : {a.sortie}")


if __name__ == "__main__":
    main()
