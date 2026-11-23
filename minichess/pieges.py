"""Banque de positions-pièges sur le 5×5 : test direct de l'hypothèse des pièges peu profonds.

Idée (Ramanujan, Sabharwal & Selman, 2010) : un « piège » est un coup qui semble anodin
mais qui perd beaucoup de matériel face à la meilleure réponse adverse, quelques coups
plus loin. On construit des positions contenant au moins un tel coup, on calcule la
valeur « vraie » de chaque coup avec un alpha-bêta profond, puis on mesure à quelle
fréquence chaque méthode tombe dans un piège (= « gaffe »).

Définitions :
- valeur d'un coup  = alpha-bêta profondeur PROF_REF + quiescence (point de vue du joueur au trait)
- coup piège        = valeur <= meilleure valeur - SEUIL (3 pions par défaut)
- niveau du piège   = 1 si la réfutation est visible en regardant UNE réponse adverse,
                      2 si elle demande 2 réponses (minimax sans quiescence, prof. 2 ou 4)

Exemple :
    python -m minichess.pieges --generer 200 --fichier donnees/pieges.json
    python -m minichess.pieges --fichier donnees/pieges.json --joueurs B1 B2 M1 M2 --budget 5000
"""

import argparse
import json
import random
from collections import defaultdict
from multiprocessing import Pool

from .evaluation import MAT
from .gardner import JeuGardner
from .joueurs import creer_joueur, JoueurAlphaBeta
from .joueurs.alphabeta import INF

PROF_REF = 4
SEUIL = 300
PLAFOND = 2000   # un mat compte comme une perte de 20 pions (évite des moyennes infinies)


def _borner(v):
    return max(-PLAFOND, min(PLAFOND, v))


def valeurs_des_coups(jeu, prof=PROF_REF, quiescence=True):
    ab = JoueurAlphaBeta(quiescence=quiescence)
    vals = {}
    for c in jeu.coups_legaux():
        vals[jeu.coup_vers_texte(c)] = _borner(-ab.evaluer_position(jeu.jouer(c), prof - 1, 10 ** 9))
    return vals


def _vers_texte(jeu):
    lignes = str(jeu).split("\n")[:5]
    return ["".join(l[3:].split()) for l in lignes]


def _position_aleatoire(rng):
    """Partie mi-alpha-bêta mi-hasard, arrêtée à une longueur aléatoire."""
    ab = JoueurAlphaBeta()
    jeu = JeuGardner()
    for _ in range(rng.randint(4, 30)):
        if jeu.est_fini():
            return None
        coups = jeu.coups_legaux()
        coup = rng.choice(coups) if rng.random() < 0.3 else ab.choisir_coup(jeu, 200)
        jeu = jeu.jouer(coup)
    return None if jeu.est_fini() else jeu


def _candidat(graine):
    rng = random.Random(graine)
    jeu = _position_aleatoire(rng)
    if jeu is None or len(jeu.coups_legaux()) < 3:
        return None
    vals = valeurs_des_coups(jeu)
    meilleure = max(vals.values())
    if meilleure >= MAT // 2 or meilleure <= -PLAFOND:   # position déjà décidée : sans intérêt
        return None
    pieges = [c for c, v in vals.items() if v <= meilleure - SEUIL]
    if not pieges or len(pieges) == len(vals):
        return None
    # niveau : réfutation visible à profondeur 2 (niveau 1) ou seulement à 4 (niveau 2)
    v2 = valeurs_des_coups(jeu, prof=2, quiescence=False)
    m2 = max(v2.values())
    niveau = 1 if any(v2[c] <= m2 - SEUIL for c in pieges) else 2
    return {"plateau": _vers_texte(jeu), "trait": jeu.trait, "valeurs": vals,
            "pieges": pieges, "niveau": niveau, "graine": graine}


def generer(n, graine=0, processus=1):
    banque, g = [], graine * 100_000
    with Pool(processus) as pool:
        while len(banque) < n:
            lot = list(range(g, g + 4 * processus * 4))
            g += len(lot)
            for p in pool.map(_candidat, lot):
                if p and len(banque) < n:
                    banque.append(p)
            print(f"  {len(banque)}/{n} positions", flush=True)
    return banque


def _tester(args):
    spec, pos, budget, graine = args
    jeu = JeuGardner.depuis_texte(pos["plateau"], pos["trait"])
    joueur = creer_joueur(spec)
    if hasattr(joueur, "rng"):
        joueur.rng.seed(graine)
    coup = jeu.coup_vers_texte(joueur.choisir_coup(jeu, budget))
    perte = max(pos["valeurs"].values()) - pos["valeurs"][coup]
    return spec, pos["niveau"], coup in pos["pieges"], perte


def evaluer(joueurs, banque, budget, processus=1):
    taches = [(j, p, budget, i) for j in joueurs for i, p in enumerate(banque)]
    with Pool(processus) as pool:
        res = pool.map(_tester, taches)
    stats = defaultdict(lambda: [0, 0, 0.0])   # (joueur, niveau) -> [gaffes, total, perte]
    for spec, niveau, gaffe, perte in res:
        for cle in ((spec, "tous"), (spec, f"niveau {niveau}")):
            stats[cle][0] += gaffe
            stats[cle][1] += 1
            stats[cle][2] += perte
    return stats


def main():
    p = argparse.ArgumentParser(description="Positions-pièges sur le 5×5.")
    p.add_argument("--fichier", default="donnees/pieges.json")
    p.add_argument("--generer", type=int, help="générer N positions dans --fichier")
    p.add_argument("--joueurs", nargs="*")
    p.add_argument("--budget", type=int, default=5000)
    p.add_argument("--processus", type=int, default=1)
    p.add_argument("--graine", type=int, default=0)
    a = p.parse_args()
    if a.generer:
        banque = generer(a.generer, a.graine, a.processus)
        with open(a.fichier, "w") as f:
            json.dump(banque, f, indent=1)
        n1 = sum(b["niveau"] == 1 for b in banque)
        print(f"{len(banque)} positions ({n1} de niveau 1, {len(banque) - n1} de niveau 2) -> {a.fichier}")
    if a.joueurs:
        banque = json.load(open(a.fichier))
        stats = evaluer(a.joueurs, banque, a.budget, a.processus)
        print(f"\n{'Joueur':<22} {'Positions':<10} {'Gaffes':>12} {'Taux':>7} {'Perte moy.':>11}")
        for (j, niv), (g, t, perte) in sorted(stats.items()):
            print(f"{j:<22} {niv:<10} {g:>5} / {t:<5} {g / t:>7.1%} {perte / t:>9.0f} cp")


if __name__ == "__main__":
    main()
