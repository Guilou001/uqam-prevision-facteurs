"""Les deux sources du travail : le taux de chômage américain et la grande base FRED-MD.

Le carnet de 2021 lisait deux fichiers déposés à la main, `UNRATE.csv` et `FactorModel.csv`. Les deux
se retéléchargent, le premier tel quel, le second dans son millésime courant faute de pouvoir obtenir
celui de septembre 2021.

Une précision s'impose sur la variable prédite. Le texte de 2021 parle de « la première différence du
taux de chômage » et sa colonne s'appelle `UNRATE_PCH`, deux noms qui ne désignent pas la même chose :
la différence première retranche le taux du mois précédent, la variation en pourcentage le divise. Les
chiffres du travail tranchent. Sa moyenne historique de -0,001925 sur 1961-2021 est celle de la
différence première, la variation en pourcentage donnant un nombre vingt fois plus grand. C'est donc
la différence première que ce dépôt télécharge, par la transformation `chg` de FRED.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RACINE = Path("data/raw")
ENTETE = {"User-Agent": "uqam-prevision-facteurs (88989051+Guilou001@users.noreply.github.com)"}

SOURCES = {
    "chomage": ("https://fred.stlouisfed.org/graph/fredgraph.csv"
                "?id=UNRATE&cosd=1948-01-01&transformation=chg"),
    "fredmd": ("https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/"
               "fred-md/monthly/current.csv"),
}
FICHIERS = {"chomage": "unrate_chg.csv", "fredmd": "fredmd_current.csv"}

# La fenêtre du travail de 2021, en dates plutôt qu'en positions de ligne.
DEBUT = "1961-01-01"
FIN_ESTIMATION = "2014-12-01"      # dernier mois d'apprentissage
DEBUT_TEST = "2015-01-01"
FIN_TEST = "2020-01-01"            # 61 mois de test
FIN = "2021-08-01"                 # dernier mois du travail de 2021
COVID = ("2020-02-01", "2021-06-01")


@dataclass(frozen=True)
class Donnees:
    """Le chômage transformé et la base de facteurs, alignés sur la même fenêtre mensuelle."""

    chomage: pd.Series
    fredmd: pd.DataFrame

    @property
    def sans_covid(self) -> pd.Series:
        masque = (self.chomage.index >= COVID[0]) & (self.chomage.index <= COVID[1])
        return self.chomage[~masque]


def _telecharger(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    reponse = requests.get(url, headers=ENTETE, timeout=180)
    reponse.raise_for_status()
    dest.write_bytes(reponse.content)
    return dest


def fetch(racine: Path = RACINE) -> dict[str, Path]:
    """Les deux fichiers sources, écrits dans `data/raw/` et jamais commités."""
    return {cle: _telecharger(url, racine / FICHIERS[cle]) for cle, url in SOURCES.items()}


def _transformer(serie: pd.Series, tcode: int) -> pd.Series:
    """La transformation officielle de FRED-MD, code par code."""
    if tcode == 1:
        return serie
    if tcode == 2:
        return serie.diff()
    if tcode == 3:
        return serie.diff().diff()
    if tcode == 4:
        return np.log(serie)
    if tcode == 5:
        return np.log(serie).diff()
    if tcode == 6:
        return np.log(serie).diff().diff()
    if tcode == 7:
        return (serie / serie.shift(1) - 1).diff()
    raise ValueError(f"code de transformation inconnu : {tcode}")


def lire_fredmd(chemin: Path) -> pd.DataFrame:
    """Le tableau transformé par les codes de sa première ligne, indexé par mois."""
    brut = pd.read_csv(chemin)
    codes = brut.iloc[0, 1:].astype(int)
    donnees = brut.iloc[1:].copy()
    donnees[brut.columns[0]] = pd.to_datetime(donnees[brut.columns[0]])
    donnees = donnees.set_index(brut.columns[0]).astype(float)
    donnees.index.name = "date"
    return pd.DataFrame({nom: _transformer(donnees[nom], int(codes[nom])) for nom in donnees.columns})


def charger_chomage(racine: Path = RACINE, debut: str = DEBUT, fin: str | None = None) -> pd.Series:
    """La seule série du chômage, sans exiger que FRED-MD couvre la même fenêtre.

    Le millésime courant de FRED-MD s'arrête avant le dernier mois publié du chômage : pour lire le
    chômage réalisé après 2021, il faut donc pouvoir charger la série seule.
    """
    brut = pd.read_csv(racine / FICHIERS["chomage"], parse_dates=["observation_date"])
    serie = brut.set_index("observation_date").iloc[:, 0].loc[debut:fin]
    serie.index.name = "date"
    serie.name = "chomage"
    return serie


def charger(racine: Path = RACINE, debut: str = DEBUT, fin: str = FIN) -> Donnees:
    """Les deux séries sur la fenêtre du travail, les colonnes incomplètes de FRED-MD retirées."""
    chomage = charger_chomage(racine, debut, fin)
    fredmd = lire_fredmd(racine / FICHIERS["fredmd"]).loc[debut:fin]
    fredmd = fredmd.loc[:, fredmd.notna().all()]
    if len(fredmd) != len(chomage):
        raise ValueError(f"fenêtres désalignées : {len(chomage)} mois de chômage, {len(fredmd)} de FRED-MD")
    return Donnees(chomage, fredmd)
