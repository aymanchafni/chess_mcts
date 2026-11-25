"""Campagne expérimentale complète du rapport, en une commande.

    python -m minichess.experiences --etape tout --processus 4            # complet (plusieurs heures)
    python -m minichess.experiences --etape tout --rapide --processus 4   # vérification (~10 min)
    python -m minichess.experiences --etape graphiques                    # refaire les figures

Étapes (chacune écrit dans resultats/ et peut être lancée seule) :
  principal  chaque méthode (B2, M1..M5, combinaison) contre B1, même budget
  budgets    Elo contre B1 selon le budget, pour quelques méthodes
  ablation   effet de C, de la profondeur de coupure, de eps ; ablation d'alpha-bêta
  pieges     taux de gaffes sur la banque de positions-pièges (génère la banque au besoin)
  puzzles    problèmes Lichess (seulement si --puzzles chemin/vers/fichier.csv[.zst])
  graphiques figures PNG pour le rapport, à partir des CSV ci-dessus
"""

import argparse
import csv
import json
import os

from . import tournoi, pieges, puzzles

DOSSIER = "resultats"
METHODES = ["B2", "M1", "M2", "M3", "M4", "M5", "M1+M2+M3"]

CONFIGS = {
    "complet": dict(ouvertures=30, budget=10_000, budgets=[2_000, 5_000, 10_000, 20_000],
                    methodes_budget=["B2", "M2", "M1+M2+M3"], pieges=200, puzzles_n=300),
    "moyen": dict(ouvertures=10, budget=5_000, budgets=[1_000, 3_000, 10_000],
                  methodes_budget=["B2", "M2", "M1+M2+M3"], pieges=100, puzzles_n=100),
    "rapide": dict(ouvertures=3, budget=2_000, budgets=[1_000, 3_000],
                   methodes_budget=["B2", "M2"], pieges=20, puzzles_n=20),
}

# Ablation : on fait varier UN paramètre de la meilleure configuration MCTS attendue.
BASE = "uct:politique=captures,eps=0.8,coupure=4,solver=1"
ABLATIONS = {
    "c": ("C (exploration)", [0.5, 1.0, 1.4, 2.0],
          lambda v: f"uct:c={v},politique=captures,eps=0.8,coupure=4,solver=1"),
    "coupure": ("profondeur de coupure d", [0, 2, 4, 8],
                lambda v: f"uct:politique=captures,eps=0.8,coupure={v},solver=1"),
    "eps": ("ε (simulations guidées)", [0.0, 0.5, 0.8, 1.0],
            lambda v: f"uct:politique=captures,eps={v},coupure=4,solver=1"),
}
ABLATION_AB = ["alphabeta:quiescence=0", "alphabeta:mvv_lva=0", "alphabeta:tt=0"]


def _chemin(nom):
    os.makedirs(DOSSIER, exist_ok=True)
    return os.path.join(DOSSIER, nom)


def _ecrire(nom, lignes):
    if not lignes:
        return
    with open(_chemin(nom), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)
    print(f"  -> {_chemin(nom)}")


def _gauntlet(joueurs, cfg, budget, processus, etiquette, graine=0):
    print(f"\n[{etiquette}] {len(joueurs)} joueur(s) contre B1, budget {budget}, "
          f"{2 * cfg['ouvertures']} parties chacun")
    res = tournoi.lancer_tournoi(joueurs, "gardner", cfg["ouvertures"], 3, budget,
                                 processus, graine, contre="B1")
    resume = tournoi.resumer(joueurs, res, contre="B1")
    tournoi.afficher_resume(resume)
    return res, resume


def _lignes_resume(resume, **extra):
    return [{"methode": j1, **extra, **{k: (round(v, 4) if isinstance(v, float) else v)
                                         for k, v in s.items()}}
            for (j1, _), s in resume.items()]


# ------------------------------------------------------------------- étapes
def etape_principal(cfg, processus):
    res, resume = _gauntlet(METHODES, cfg, cfg["budget"], processus, "principal")
    tournoi.sauver_csv(res, _chemin("principal_parties.csv"))
    _ecrire("principal.csv", _lignes_resume(resume, budget=cfg["budget"]))


def etape_budgets(cfg, processus):
    lignes, parties = [], []
    for b in cfg["budgets"]:
        res, resume = _gauntlet(cfg["methodes_budget"], cfg, b, processus, f"budget {b}")
        parties += res
        lignes += _lignes_resume(resume, budget=b)
    tournoi.sauver_csv(parties, _chemin("budgets_parties.csv"))
    _ecrire("budgets.csv", lignes)


def etape_ablation(cfg, processus):
    lignes = []
    for param, (_, valeurs, fabrique) in ABLATIONS.items():
        joueurs = [fabrique(v) for v in valeurs]
        _, resume = _gauntlet(joueurs, cfg, cfg["budget"], processus, f"ablation {param}")
        for v, j in zip(valeurs, joueurs):
            s = resume[(j, "B1")]
            lignes.append({"parametre": param, "valeur": v, "methode": j,
                           **{k: (round(x, 4) if isinstance(x, float) else x) for k, x in s.items()}})
    _, resume = _gauntlet(ABLATION_AB, cfg, cfg["budget"], processus, "ablation alpha-bêta")
    for (j, _), s in resume.items():
        lignes.append({"parametre": "alphabeta", "valeur": j.split(":")[1], "methode": j,
                       **{k: (round(x, 4) if isinstance(x, float) else x) for k, x in s.items()}})
    _ecrire("ablation.csv", lignes)


def etape_pieges(cfg, processus):
    fichier = _chemin("pieges_banque.json")
    if not os.path.exists(fichier):
        print(f"\n[pièges] génération de {cfg['pieges']} positions")
        with open(fichier, "w") as f:
            json.dump(pieges.generer(cfg["pieges"], 0, processus), f, indent=1)
    banque = json.load(open(fichier))
    joueurs = ["B1"] + METHODES
    print(f"\n[pièges] {len(banque)} positions, {len(joueurs)} joueurs, budget {cfg['budget']}")
    stats = pieges.evaluer(joueurs, banque, cfg["budget"], processus)
    lignes = [{"methode": j, "positions": niv, "gaffes": g, "total": t,
               "taux_gaffes": round(g / t, 4), "perte_moyenne_cp": round(p / t, 1)}
              for (j, niv), (g, t, p) in stats.items()]
    for l in sorted(lignes, key=lambda l: (l["positions"], l["methode"])):
        print(f"  {l['methode']:<12} {l['positions']:<10} {l['taux_gaffes']:>6.1%}  {l['perte_moyenne_cp']:>6} cp")
    _ecrire("pieges.csv", lignes)


def etape_puzzles(cfg, processus, fichier):
    if not fichier:
        print("\n[puzzles] ignoré : télécharger lichess_db_puzzle.csv.zst puis passer --puzzles <fichier>")
        return
    pz = puzzles.charger_puzzles(fichier, ["mateIn1", "mateIn2", "hangingPiece", "fork"],
                                 elo_max=1800, n=cfg["puzzles_n"])
    joueurs = ["B1"] + METHODES
    print(f"\n[puzzles] {len(pz)} problèmes, {len(joueurs)} joueurs")
    _, par_theme = puzzles.evaluer(joueurs, pz, cfg["budget"], processus,
                                   {"mateIn1", "mateIn2", "hangingPiece", "fork"})
    lignes = [{"methode": j, "theme": th, "reussis": ok, "total": tot, "taux": round(ok / tot, 4)}
              for (j, th), (ok, tot) in par_theme.items()]
    _ecrire("puzzles.csv", lignes)


# --------------------------------------------------------------- graphiques
# Palette catégorielle de référence (ordre fixe, jamais recyclé), encres neutres.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
ENCRE, ENCRE_2, GRILLE, FOND = "#1f1f1e", "#6b6a64", "#e4e3de", "#fcfcfb"


def _style(ax):
    ax.set_facecolor(FOND)
    for cote in ("top", "right"):
        ax.spines[cote].set_visible(False)
    for cote in ("left", "bottom"):
        ax.spines[cote].set_color(GRILLE)
    ax.tick_params(colors=ENCRE_2, labelsize=9)
    ax.grid(axis="y", color=GRILLE, linewidth=0.8)
    ax.set_axisbelow(True)


def _lire(nom):
    chemin = _chemin(nom)
    if not os.path.exists(chemin):
        return None
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _barres_elo(ax, noms, elo, bas, haut, titre, scores):
    y = list(range(len(noms)))
    ax.barh(y, elo, color=SERIES[0], height=0.55)
    ax.errorbar(elo, y, xerr=[[e - b for e, b in zip(elo, bas)], [h - e for e, h in zip(elo, haut)]],
                fmt="none", ecolor=ENCRE, elinewidth=1, capsize=3)
    ax.axvline(0, color=ENCRE_2, linewidth=1)
    x_texte = max(max(haut), 0) + 40   # colonne de scores à droite de toutes les barres d'erreur
    for yi, sc in zip(y, scores):      # le score réel, car un score de 0 % borne l'Elo à -1200
        ax.text(x_texte, yi, f"score {sc:.0%}", va="center", fontsize=8, color=ENCRE_2)
    ax.set_xlim(right=x_texte + 260)
    ax.set_yticks(y, noms)
    ax.invert_yaxis()
    ax.grid(axis="x", color=GRILLE, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Elo relatif à alpha-bêta (B1), IC 95 %", color=ENCRE_2)
    ax.set_title(titre, color=ENCRE, loc="left", fontsize=11)


def etape_graphiques():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    faits = []
    d = _lire("principal.csv")
    if d:
        fig, ax = plt.subplots(figsize=(7, 3.8), facecolor=FOND)
        _style(ax)
        _barres_elo(ax, [r["methode"] for r in d], [float(r["elo"]) for r in d],
                    [float(r["elo_min"]) for r in d], [float(r["elo_max"]) for r in d],
                    f"Force de chaque variante MCTS contre B1 (budget {d[0]['budget']})",
                    [float(r["score"]) for r in d])
        fig.tight_layout(); fig.savefig(_chemin("fig_principal.png"), dpi=200); faits.append("fig_principal.png")

    d = _lire("budgets.csv")
    if d:
        fig, ax = plt.subplots(figsize=(7, 4), facecolor=FOND)
        _style(ax)
        methodes = list(dict.fromkeys(r["methode"] for r in d))
        for i, m in enumerate(methodes):
            pts = sorted((int(r["budget"]), float(r["elo"])) for r in d if r["methode"] == m)
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=SERIES[i], linewidth=2, marker="o", markersize=5, label=m)
        ax.axhline(0, color=ENCRE_2, linewidth=1)
        ax.set_xscale("log")
        budgets = sorted({int(r["budget"]) for r in d})
        ax.set_xticks(budgets, [f"{b:,}".replace(",", " ") for b in budgets])
        ax.minorticks_off()
        fig.text(0.01, 0.01, "−1200 = score de 0 % (Elo non borné)", fontsize=8, color=ENCRE_2)
        ax.set_xlabel("Budget par coup (appels à jouer(), échelle log)", color=ENCRE_2)
        ax.set_ylabel("Elo relatif à B1", color=ENCRE_2)
        ax.set_title("L'écart avec alpha-bêta selon le budget", color=ENCRE, loc="left", fontsize=11)
        ax.legend(frameon=False, fontsize=9)
        fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(_chemin("fig_budgets.png"), dpi=200); faits.append("fig_budgets.png")

    d = _lire("ablation.csv")
    if d:
        fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), facecolor=FOND, sharey=True)
        for ax, (param, (etiq, _, _)) in zip(axes, ABLATIONS.items()):
            _style(ax)
            pts = [(float(r["valeur"]), float(r["elo"]), float(r["elo_min"]), float(r["elo_max"]))
                   for r in d if r["parametre"] == param]
            xs, ys, bs, hs = zip(*pts)
            ax.fill_between(xs, bs, hs, color=SERIES[0], alpha=0.15, linewidth=0)
            ax.plot(xs, ys, color=SERIES[0], linewidth=2, marker="o", markersize=5)
            ax.axhline(0, color=ENCRE_2, linewidth=1)
            ax.set_xlabel(etiq, color=ENCRE_2)
        axes[0].set_ylabel("Elo relatif à B1", color=ENCRE_2)
        fig.suptitle("Ablation de la configuration M1+M2+M3", color=ENCRE, x=0.01, ha="left", fontsize=11)
        fig.tight_layout(); fig.savefig(_chemin("fig_ablation.png"), dpi=200); faits.append("fig_ablation.png")

    d = _lire("pieges.csv")
    if d:
        fig, ax = plt.subplots(figsize=(7, 3.8), facecolor=FOND)
        _style(ax)
        methodes = list(dict.fromkeys(r["methode"] for r in d))
        niveaux = sorted({r["positions"] for r in d if r["positions"] != "tous"})
        larg = 0.8 / len(niveaux)
        for i, niv in enumerate(niveaux):
            vals = [next((float(r["taux_gaffes"]) * 100 for r in d
                          if r["methode"] == m and r["positions"] == niv), 0) for m in methodes]
            xs = [k + (i - (len(niveaux) - 1) / 2) * larg for k in range(len(methodes))]
            ax.bar(xs, vals, width=larg * 0.92, color=SERIES[i], label=f"pièges de {niv}")
        ax.set_xticks(range(len(methodes)), methodes)
        ax.set_ylabel("Taux de gaffes (%)", color=ENCRE_2)
        ax.set_title("Qui tombe dans les pièges peu profonds ?", color=ENCRE, loc="left", fontsize=11)
        ax.legend(frameon=False, fontsize=9)
        fig.tight_layout(); fig.savefig(_chemin("fig_pieges.png"), dpi=200); faits.append("fig_pieges.png")

    d = _lire("puzzles.csv")
    if d:
        fig, ax = plt.subplots(figsize=(7, 3.8), facecolor=FOND)
        _style(ax)
        tous = [r for r in d if r["theme"] == "TOUS"]
        ax.bar(range(len(tous)), [float(r["taux"]) * 100 for r in tous], color=SERIES[0], width=0.6)
        ax.set_xticks(range(len(tous)), [r["methode"] for r in tous])
        ax.set_ylabel("Problèmes résolus (%)", color=ENCRE_2)
        ax.set_title("Problèmes tactiques Lichess (échecs complets)", color=ENCRE, loc="left", fontsize=11)
        fig.tight_layout(); fig.savefig(_chemin("fig_puzzles.png"), dpi=200); faits.append("fig_puzzles.png")

    print("\n[graphiques] " + (", ".join(faits) if faits else "aucun CSV trouvé"))


def main():
    p = argparse.ArgumentParser(description="Campagne expérimentale du rapport.")
    p.add_argument("--etape", default="tout",
                   choices=["tout", "principal", "budgets", "ablation", "pieges", "puzzles", "graphiques"])
    p.add_argument("--rapide", action="store_true", help="petite version pour vérifier que tout marche")
    p.add_argument("--moyen", action="store_true", help="version intermédiaire (~45 min sur 2 cœurs)")
    p.add_argument("--processus", type=int, default=os.cpu_count() or 1)
    p.add_argument("--puzzles", help="chemin vers lichess_db_puzzle.csv(.zst)")
    p.add_argument("--dossier", default="resultats")
    a = p.parse_args()

    global DOSSIER
    DOSSIER = a.dossier
    cfg = CONFIGS["rapide" if a.rapide else "moyen" if a.moyen else "complet"]
    etapes = ["principal", "budgets", "ablation", "pieges", "puzzles", "graphiques"] \
        if a.etape == "tout" else [a.etape]
    for e in etapes:
        if e == "principal":
            etape_principal(cfg, a.processus)
        elif e == "budgets":
            etape_budgets(cfg, a.processus)
        elif e == "ablation":
            etape_ablation(cfg, a.processus)
        elif e == "pieges":
            etape_pieges(cfg, a.processus)
        elif e == "puzzles":
            etape_puzzles(cfg, a.processus, a.puzzles)
        elif e == "graphiques":
            etape_graphiques()


if __name__ == "__main__":
    main()
