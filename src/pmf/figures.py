"""Les figures, redessinées depuis les tables de `results/tables/`.

Aucun titre n'est écrit à la main : chacun se déduit du fichier de résultats qu'il commente.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pmf.modeles import LIBELLES, ORDRE_MODELES

OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]


def use_style():
    import matplotlib as mpl
    from cycler import cycler
    from matplotlib.ticker import FuncFormatter

    mpl.rcParams.update({
        "figure.dpi": 200, "savefig.dpi": 200, "figure.constrained_layout.use": True,
        "font.size": 10, "axes.titlesize": 11, "axes.prop_cycle": cycler(color=OKABE_ITO),
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5,
        "legend.frameon": False, "lines.linewidth": 1.4,
    })
    return FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))


def _fr(x: float, n: int = 3) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def fig_erreurs(relatif: pd.DataFrame, dest: Path) -> Path:
    """Une courbe par modèle, l'erreur relative au repère en fonction de l'horizon."""
    fr = use_style()
    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    colonnes = [c for c in ORDRE_MODELES if c in relatif.columns and c != "ar1"]
    horizons = np.arange(1, len(relatif) + 1)
    for k, cle in enumerate(colonnes):
        ax.plot(horizons, relatif[cle], marker="o", ms=3.5, color=OKABE_ITO[k % len(OKABE_ITO)],
                label=LIBELLES[cle])
    ax.axhline(1.0, color="black", lw=1.0, ls="--")
    ax.set_xlabel("Horizon de prévision, en mois")
    ax.set_ylabel("Erreur quadratique moyenne, rapportée au repère")
    ax.set_xticks(horizons)
    ax.yaxis.set_major_formatter(fr)
    ax.legend(fontsize=8.5, ncols=2)
    meilleur = relatif[colonnes].min().idxmin()
    horizon = int(relatif[meilleur].idxmin()[1:])
    ax.set_title(f"Le meilleur couple est le {LIBELLES[meilleur]} à l'horizon {horizon}, "
                 f"à {_fr(relatif[meilleur].min())} du repère\n"
                 "La ligne pointillée est l'autorégressif d'ordre 1 à l'horizon 1", fontsize=10.5)
    fig.savefig(dest)
    plt.close(fig)
    return dest


def fig_serie(serie: pd.Series, covid: tuple[str, str], dest: Path) -> Path:
    """La variable prédite, et la fenêtre que le travail met de côté."""
    fr = use_style()
    fig, ax = plt.subplots(figsize=(9.6, 4.2))
    ax.plot(serie.index, serie.to_numpy(), color=OKABE_ITO[0], lw=0.9)
    ax.axvspan(pd.Timestamp(covid[0]), pd.Timestamp(covid[1]), color=OKABE_ITO[3], alpha=0.18,
               label="fenêtre retirée dans la seconde variante")
    ax.axhline(0.0, color="black", lw=0.8)
    ax.set_ylabel("Variation mensuelle du taux de chômage\n(points de pourcentage)", fontsize=9.5)
    ax.yaxis.set_major_formatter(fr)
    ax.legend(fontsize=9)
    pointe = serie.abs().idxmax()
    ax.set_title(f"Chômage américain, {serie.index[0]:%Y-%m} à {serie.index[-1]:%Y-%m} : "
                 f"la plus forte variation vaut {_fr(serie.loc[pointe], 1)} point en "
                 f"{pointe:%Y-%m}", fontsize=10.5)
    fig.savefig(dest)
    plt.close(fig)
    return dest


def fig_futur(previsions: pd.DataFrame, realise: pd.Series, dest: Path) -> Path:
    """Le pari de 2021 pour l'année suivante, et ce que le chômage a fait."""
    fr = use_style()
    modeles = sorted({c.rsplit("_avec", 1)[0].rsplit("_sans", 1)[0] for c in previsions.columns})
    fig, axes = plt.subplots(1, len(modeles), figsize=(4.0 * len(modeles), 4.0), sharey=True)
    axes = np.atleast_1d(axes)
    cible = realise.reindex(previsions.index)
    for ax, cle in zip(axes, modeles, strict=False):
        ax.plot(previsions.index, cible.to_numpy(), color="black", lw=1.6, label="réalisé")
        ax.plot(previsions.index, previsions[f"{cle}_avec_covid"], color=OKABE_ITO[1],
                marker="o", ms=3, label="avec la Covid")
        ax.plot(previsions.index, previsions[f"{cle}_sans_covid"], color=OKABE_ITO[2],
                marker="s", ms=3, label="sans la Covid")
        ax.set_title(LIBELLES[cle], fontsize=10)
        ax.tick_params(axis="x", rotation=45, labelsize=7.5)
        ax.yaxis.set_major_formatter(fr)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Variation mensuelle du taux de chômage\n(points de pourcentage)", fontsize=9)
    fig.suptitle(f"Prévisions faites en 2021 pour {previsions.index[0]:%Y-%m} à "
                 f"{previsions.index[-1]:%Y-%m}, contre le chômage réalisé", fontsize=11)
    fig.savefig(dest)
    plt.close(fig)
    return dest


def toutes(out: Path = Path("results")) -> list[Path]:
    """Toutes les figures que les tables présentes permettent de dessiner."""
    from pmf import donnees

    tables, figs = out / "tables", out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    ecrites = []

    chemin = tables / "eqm_relatif.csv"
    if chemin.exists():
        ecrites.append(fig_erreurs(pd.read_csv(chemin, index_col=0), figs / "erreurs_par_horizon.png"))

    d = donnees.charger()
    ecrites.append(fig_serie(d.chomage, donnees.COVID, figs / "chomage_et_covid.png"))

    chemin = tables / "previsions_2021_2022.csv"
    if chemin.exists():
        previsions = pd.read_csv(chemin, index_col=0, parse_dates=True)
        realise = donnees.charger_chomage(fin=None)
        ecrites.append(fig_futur(previsions, realise, figs / "pari_de_2021.png"))
    return ecrites
