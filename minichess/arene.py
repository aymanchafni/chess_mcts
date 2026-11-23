"""Faire jouer deux joueurs, et générer des positions de départ variées."""

import random
import time

from .gardner import JeuGardner
from .echecs import JeuEchecs

JEUX = {"gardner": JeuGardner, "echecs": JeuEchecs}


def jouer_partie(blanc, noir, depart, budget, verbeux=False):
    """Joue une partie complète. Renvoie un dict (résultat du point de vue des blancs)."""
    blanc.nouvelle_partie()
    noir.nouvelle_partie()
    jeu, coups, t0 = depart, [], time.perf_counter()
    while not jeu.est_fini():
        joueur = blanc if jeu.trait == 1 else noir
        coup = joueur.choisir_coup(jeu, budget)
        if coup not in jeu.coups_legaux():
            raise RuntimeError(f"{joueur} a joué un coup illégal : {coup}")
        coups.append(jeu.coup_vers_texte(coup))
        jeu = jeu.jouer(coup)
        if verbeux:
            print(f"{coups[-1]}\n{jeu}\n")
    return {
        "resultat": jeu.resultat(),
        "demi_coups": len(coups),
        "duree_s": round(time.perf_counter() - t0, 3),
        "coups": " ".join(coups),
    }


def generer_ouvertures(nom_jeu, n, demi_coups=2, graine=0):
    """`n` positions distinctes obtenues en jouant `demi_coups` coups au hasard.
    Sans cela, deux joueurs déterministes joueraient toujours la même partie.
    Pour Gardner : 2 demi-coups -> 49 positions possibles, 3 -> environ 450."""
    rng = random.Random(graine)
    vues, ouvertures, essais = set(), [], 0
    while len(ouvertures) < n and essais < 50 * n:
        essais += 1
        jeu, textes = JEUX[nom_jeu](), []
        for _ in range(demi_coups):
            if jeu.est_fini():
                break
            coup = rng.choice(jeu.coups_legaux())
            textes.append(jeu.coup_vers_texte(coup))
            jeu = jeu.jouer(coup)
        if not jeu.est_fini() and jeu.cle() not in vues:
            vues.add(jeu.cle())
            ouvertures.append(textes)
    return ouvertures


def position_depuis_ouverture(nom_jeu, textes):
    jeu = JEUX[nom_jeu]()
    for t in textes:
        jeu = jeu.jouer(jeu.texte_vers_coup(t))
    return jeu
