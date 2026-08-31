"""Le pari de 2021, et sa réponse.

Le travail se terminait sur une question ouverte : faut-il retirer la Covid des données pour prévoir
la suite, et « il faudra attendre quelques mois pour voir la meilleure approche ». Les mois ont passé.
Ce module rejoue les prévisions de septembre 2021 à septembre 2022, avec et sans la période
2020-02 à 2021-06, puis les confronte au chômage réellement observé.

Trois des six modèles sont rejoués, ceux qui ne demandent aucune prévision auxiliaire : la moyenne
historique, l'autorégressif direct d'ordre 4 et l'ARMA. Les trois autres, à facteurs, ARDL et VAR,
auraient besoin qu'on prévoie d'abord leurs propres variables explicatives, ce que le carnet de 2021
faisait par des ARMA auxiliaires. Ils ne sont pas prolongés ici, et c'est déclaré.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.api import AutoReg
from statsmodels.tsa.arima.model import ARIMA

from pmf.modeles import ORDRE_AR, ORDRE_ARMA

DEBUT_PREVISION = "2021-09-01"
FIN_PREVISION = "2022-09-01"
HORIZON_RETENU = 4          # l'horizon que le travail retient pour l'autorégressif


def _moyenne(serie: pd.Series, mois: int) -> np.ndarray:
    return np.repeat(float(serie.mean()), mois)


def _autoregressif(serie: pd.Series, mois: int) -> np.ndarray:
    retards = list(range(HORIZON_RETENU, HORIZON_RETENU + ORDRE_AR))
    ajuste = AutoReg(serie.reset_index(drop=True), lags=retards).fit()
    return np.asarray(ajuste.predict(len(serie), len(serie) + mois - 1, dynamic=True))


def _arma(serie: pd.Series, mois: int) -> np.ndarray:
    ajuste = ARIMA(serie.reset_index(drop=True), order=(ORDRE_ARMA[0], 0, ORDRE_ARMA[1])).fit()
    return np.asarray(ajuste.predict(len(serie), len(serie) + mois - 1))


MODELES = {"moyenne": _moyenne, "ar4": _autoregressif, "arma": _arma}


def prevoir(donnees, mois: int = 13) -> pd.DataFrame:
    """Les prévisions des trois modèles, avec et sans la Covid, sur les treize mois demandés."""
    warnings.filterwarnings("ignore")
    dates = pd.date_range(DEBUT_PREVISION, periods=mois, freq="MS")
    colonnes = {}
    for cle, fonction in MODELES.items():
        colonnes[f"{cle}_avec_covid"] = fonction(donnees.chomage, mois)
        colonnes[f"{cle}_sans_covid"] = fonction(donnees.sans_covid, mois)
    return pd.DataFrame(colonnes, index=dates)


def confronter(previsions: pd.DataFrame, realise: pd.Series) -> pd.DataFrame:
    """L'erreur quadratique moyenne de chaque variante contre le chômage réellement observé."""
    cible = realise.reindex(previsions.index)
    if cible.isna().any():
        raise ValueError("le chômage réalisé ne couvre pas toute la fenêtre de prévision")
    lignes = []
    for colonne in previsions.columns:
        modele, variante = colonne.rsplit("_", 2)[0], colonne.split("_", 1)[1]
        erreur = float(((previsions[colonne] - cible) ** 2).mean())
        lignes.append({"modele": modele, "variante": variante, "eqm": erreur,
                       "erreur_moyenne": float((previsions[colonne] - cible).mean())})
    return pd.DataFrame(lignes)
