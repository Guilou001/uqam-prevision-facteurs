"""Les six modèles du travail, plus le repère auquel tout est comparé.

La prévision est dite **directe**. Pour prévoir à l'horizon h, on ne prédit pas h fois de suite un
modèle à un mois. On estime un modèle qui relie directement la valeur du mois t à celles des mois
t - h et antérieurs. Le carnet de 2021 l'obtient en ne gardant que les retards h + 1 et suivants, puis
en prédisant le mois qui suit la fin de l'échantillon. Ce portage garde ce montage.

Chaque modèle est réestimé à chaque fenêtre, 12 horizons fois 61 fenêtres, soit 732 estimations par
modèle. La fenêtre s'allonge d'un mois à chaque tour : le modèle voit toujours tout le passé
disponible, jamais le futur.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.multivariate.pca import PCA
from statsmodels.tsa.api import ARDL, VAR, AutoReg
from statsmodels.tsa.arima.model import ARIMA

HORIZONS = 12
FENETRES = 61

# Les ordres retenus par le critère BIC dans le travail de 2021, gardés tels quels.
ORDRE_AR = 4
ORDRE_ARMA = (1, 2)
COMPOSANTES = 2
RETARDS_FACTEURS = {"comp_0": 2, "comp_1": 5}
EXOGENES_ARDL = ("CLAIMSx", "PAYEMS")
RETARDS_ARDL = {"CLAIMSx": 3, "PAYEMS": 2}
EXOGENE_VAR = "CLAIMSx"
MAXLAGS_VAR = 12

LIBELLES = {
    "moyenne": "Moyenne historique",
    "ar1": "Autorégressif d'ordre 1 (repère)",
    "ar4": "Autorégressif direct d'ordre 4",
    "facteurs": "Modèle à facteurs",
    "arma": "ARMA (1, 2)",
    "ardl": "ARDL",
    "var": "VAR",
}
ORDRE_MODELES = ["moyenne", "ar1", "ar4", "facteurs", "arma", "ardl", "var"]


@dataclass
class Decoupage:
    """Les positions que le carnet de 2021 codait en dur, recalculées depuis les dates."""

    debut_test: int          # première ligne de l'échantillon de test
    fenetres: int            # nombre de fenêtres glissantes

    @classmethod
    def depuis(cls, index: pd.DatetimeIndex, debut_test: str, fin_test: str) -> Decoupage:
        i = int(index.get_loc(pd.Timestamp(debut_test)))
        j = int(index.get_loc(pd.Timestamp(fin_test)))
        return cls(i, j - i + 1)


def _sans_avertissements():
    warnings.filterwarnings("ignore")


def moyenne(y: pd.Series, d: Decoupage, h: int, i: int, **_) -> float:
    """La moyenne de tout le passé disponible, raccourcie de h mois comme en 2021."""
    return float(y.iloc[: d.debut_test + i - h].mean())


def autoregressif(y: pd.Series, d: Decoupage, h: int, i: int, ordre: int = 1, **_) -> float:
    """Un autorégressif direct sur les retards h + 1 à h + ordre."""
    fenetre = y.iloc[: d.debut_test + i]
    modele = AutoReg(fenetre, lags=list(range(h + 1, h + 1 + ordre))).fit()
    return float(modele.predict(len(fenetre), len(fenetre)).iloc[0])


def arma(y: pd.Series, d: Decoupage, h: int, i: int, **_) -> float:
    """Un ARMA dont la partie autorégressive ne garde que le retard h + 1."""
    fenetre = y.iloc[: d.debut_test + i]
    modele = ARIMA(fenetre, order=([h + 1], 0, ORDRE_ARMA[1])).fit()
    return float(modele.predict(len(fenetre), len(fenetre)).iloc[0])


def _ardl(fenetre: pd.Series, exog: pd.DataFrame, exog_futur: pd.DataFrame, h: int,
          retards: dict) -> float:
    modele = ARDL(fenetre, lags=[h + 1], exog=exog, order=retards, causal=True).fit()
    return float(modele.predict(len(fenetre), len(fenetre), exog_oos=exog_futur).iloc[0])


def facteurs(y: pd.Series, d: Decoupage, h: int, i: int, X: pd.DataFrame = None,
             composantes: int = COMPOSANTES, **_) -> float:
    """Deux composantes principales de FRED-MD, plus un retard du chômage.

    Les composantes sont recalculées à chaque fenêtre sur le passé disponible plus le mois à prévoir,
    ce que le carnet de 2021 fait aussi. La dernière ligne des composantes sert de valeur exogène
    connue au moment de la prévision.
    """
    fenetre = y.iloc[: d.debut_test + i]
    bloc = X.iloc[: d.debut_test + i + 1]
    composantes_estimees = PCA(bloc, ncomp=composantes, missing="fill-em").factors
    exog = composantes_estimees.iloc[:-1].set_axis(fenetre.index)
    futur = composantes_estimees.iloc[-1:].set_axis(X.index[d.debut_test + i : d.debut_test + i + 1])
    return _ardl(fenetre, exog, futur, h, RETARDS_FACTEURS)


def ardl(y: pd.Series, d: Decoupage, h: int, i: int, X: pd.DataFrame = None, **_) -> float:
    """Le chômage expliqué par ses retards et par deux séries de FRED-MD."""
    fenetre = y.iloc[: d.debut_test + i]
    bloc = X.loc[:, list(EXOGENES_ARDL)].iloc[: d.debut_test + i + 1]
    exog = bloc.iloc[:-1].set_axis(fenetre.index)
    return _ardl(fenetre, exog, bloc.iloc[-1:], h, RETARDS_ARDL)


def var(y: pd.Series, d: Decoupage, h: int, i: int, X: pd.DataFrame = None, **_) -> float:
    """Un vecteur autorégressif à deux variables, prolongé de h + 1 mois."""
    fenetre = pd.concat([y.iloc[: d.debut_test + i],
                         X[EXOGENE_VAR].iloc[: d.debut_test + i]], axis=1)
    ajuste = VAR(fenetre).fit(maxlags=MAXLAGS_VAR, ic="bic")
    retards = max(ajuste.k_ar, 1)
    return float(ajuste.forecast(fenetre.values[-retards:], h + 1)[-1][0])


MODELES = {"moyenne": moyenne, "ar1": lambda *a, **k: autoregressif(*a, ordre=1, **k),
           "ar4": lambda *a, **k: autoregressif(*a, ordre=ORDRE_AR, **k),
           "facteurs": facteurs, "arma": arma, "ardl": ardl, "var": var}


def prevoir(cle: str, donnees, d: Decoupage, horizons: int = HORIZONS) -> np.ndarray:
    """La matrice des prévisions d'un modèle, un horizon par ligne, une fenêtre par colonne."""
    _sans_avertissements()
    fonction = MODELES[cle]
    sortie = np.empty((horizons, d.fenetres))
    for h in range(horizons):
        for i in range(d.fenetres):
            sortie[h, i] = fonction(donnees.chomage, d, h, i, X=donnees.fredmd)
    return sortie


def erreurs(previsions: np.ndarray, realise: pd.Series) -> np.ndarray:
    """L'erreur quadratique moyenne de chaque horizon, sur les mêmes 61 mois de test."""
    cible = realise.to_numpy()
    return ((previsions - cible) ** 2).mean(axis=1)
