"""Tournois entre joueurs, avec calcul d'Elo et intervalle de confiance.

Exemples :
    python -m minichess.tournoi --joueurs alphabeta aleatoire --ouvertures 20 --budget 2000
    python -m minichess.tournoi --joueurs alphabeta "alphabeta:quiescence=0" \\
        --ouvertures 50 --budget 10000 --processus 4 --sortie resultats/ab_vs_noqs.csv

Protocole :
- Chaque ouverture est jouée DEUX fois, couleurs inversées (élimine l'avantage du trait).
- Tous les joueurs ont le même budget (appels à jouer()) par coup.
- Toutes les paires de joueurs s'affrontent (« toutes rondes »).
"""

import argparse
import csv
import itertools
import math
import os
import random
from multiprocessing import Pool

from .arene import jouer_partie, generer_ouvertures, position_depuis_ouverture
from .joueurs import creer_joueur


# ----------------------------------------------------------------- statistiques
def elo_depuis_score(s: float) -> float:
    """Différence d'Elo correspondant à un score moyen s (0..1). 0,64 -> +100 environ."""
    s = min(max(s, 1e-3), 1 - 1e-3)
    return -400.0 * math.log10(1.0 / s - 1.0)


def statistiques(scores):
    """scores : liste de 1 / 0,5 / 0 du point de vue du joueur 1."""
    n = len(scores)
    v, nul, d = scores.count(1.0), scores.count(0.5), scores.count(0.0)
    s = sum(scores) / n
    var = sum((x - s) ** 2 for x in scores) / max(n - 1, 1)
    marge = 1.96 * math.sqrt(var / n)
    return {
        "parties": n, "victoires": v, "nulles": nul, "defaites": d,
        "score": s,
        "elo": elo_depuis_score(s),
        "elo_min": elo_depuis_score(s - marge),
        "elo_max": elo_depuis_score(s + marge),
    }


# ------------------------------------------------------------------- exécution
def _partie(tache):
    blanc_spec, noir_spec, nom_jeu, ouverture, budget, graine = tache
    random.seed(graine)
    blanc, noir = creer_joueur(blanc_spec), creer_joueur(noir_spec)
    for i, j in enumerate((blanc, noir)):
        if hasattr(j, "rng"):            # rend les joueurs aléatoires reproductibles
            j.rng.seed(graine * 2 + i)
    depart = position_depuis_ouverture(nom_jeu, ouverture)
    res = jouer_partie(blanc, noir, depart, budget)
    res.update(blanc=blanc_spec, noir=noir_spec, ouverture=" ".join(ouverture),
               budget=budget, jeu=nom_jeu, graine=graine)
    return res


def paires_de(joueurs, contre=None):
    """Toutes rondes, ou (si `contre`) chaque joueur contre une référence fixe."""
    if contre:
        return [(j, contre) for j in joueurs if j != contre]
    return list(itertools.combinations(joueurs, 2))


def lancer_tournoi(joueurs, nom_jeu="gardner", nb_ouvertures=20, demi_coups_ouverture=3,
                   budget=5000, processus=1, graine=0, afficher=True, contre=None):
    ouvertures = generer_ouvertures(nom_jeu, nb_ouvertures, demi_coups_ouverture, graine)
    taches = []
    for j1, j2 in paires_de(joueurs, contre):
        for k, ouv in enumerate(ouvertures):
            g = graine * 1_000_003 + len(taches)
            taches.append((j1, j2, nom_jeu, ouv, budget, g))
            taches.append((j2, j1, nom_jeu, ouv, budget, g + 1))

    resultats = []
    if processus > 1:
        with Pool(processus) as pool:
            for i, r in enumerate(pool.imap_unordered(_partie, taches), 1):
                resultats.append(r)
                if afficher and i % max(1, len(taches) // 20) == 0:
                    print(f"  {i}/{len(taches)} parties", flush=True)
    else:
        for i, t in enumerate(taches, 1):
            resultats.append(_partie(t))
            if afficher and i % max(1, len(taches) // 20) == 0:
                print(f"  {i}/{len(taches)} parties", flush=True)
    return resultats


def resumer(joueurs, resultats, contre=None):
    """Statistiques par paire (point de vue du premier joueur de la paire)."""
    resume = {}
    for j1, j2 in paires_de(joueurs, contre):
        scores = []
        for r in resultats:
            if (r["blanc"], r["noir"]) == (j1, j2):
                scores.append((r["resultat"] + 1) / 2)
            elif (r["blanc"], r["noir"]) == (j2, j1):
                scores.append((1 - r["resultat"]) / 2)
        if scores:
            resume[(j1, j2)] = statistiques(scores)
    return resume


def afficher_resume(resume):
    l1 = max([8] + [len(a) for a, _ in resume])
    l2 = max([8] + [len(b) for _, b in resume])
    print(f"\n{'Joueur 1':<{l1}}  {'Joueur 2':<{l2}} {'V-N-D':>11} {'Score':>6} {'Elo (IC 95 %)':>22}")
    print("-" * (l1 + l2 + 45))
    for (j1, j2), s in resume.items():
        vnd = f"{s['victoires']}-{s['nulles']}-{s['defaites']}"
        if s["score"] in (0.0, 1.0):
            ic = "non borné (100 %)" if s["score"] == 1.0 else "non borné (0 %)"
        else:
            ic = f"{s['elo']:+.0f} [{s['elo_min']:+.0f}, {s['elo_max']:+.0f}]"
        print(f"{j1:<{l1}}  {j2:<{l2}} {vnd:>11} {s['score']:>6.1%} {ic:>22}")


def sauver_csv(resultats, chemin):
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    champs = ["jeu", "budget", "blanc", "noir", "resultat", "demi_coups", "duree_s",
              "ouverture", "graine", "coups"]
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        for r in resultats:
            w.writerow({k: r[k] for k in champs})


def main():
    p = argparse.ArgumentParser(description="Tournoi toutes rondes entre joueurs.")
    p.add_argument("--joueurs", nargs="+", required=True, help='ex. alphabeta "alphabeta:quiescence=0"')
    p.add_argument("--jeu", default="gardner", choices=["gardner", "echecs"])
    p.add_argument("--ouvertures", type=int, default=20, help="nb d'ouvertures (x2 parties par paire)")
    p.add_argument("--demi-coups-ouverture", type=int, default=3)
    p.add_argument("--budget", type=int, default=5000, help="appels à jouer() par coup")
    p.add_argument("--processus", type=int, default=1)
    p.add_argument("--graine", type=int, default=0)
    p.add_argument("--contre", help="référence fixe : chaque joueur ne joue que contre elle")
    p.add_argument("--sortie", help="fichier CSV (une ligne par partie)")
    a = p.parse_args()

    resultats = lancer_tournoi(a.joueurs, a.jeu, a.ouvertures, a.demi_coups_ouverture,
                               a.budget, a.processus, a.graine, contre=a.contre)
    afficher_resume(resumer(a.joueurs, resultats, a.contre))
    if a.sortie:
        sauver_csv(resultats, a.sortie)
        print(f"\nRésultats détaillés : {a.sortie}")


if __name__ == "__main__":
    main()
