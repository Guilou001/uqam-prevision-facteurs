"""Les identités du travail vérifiées sans réseau : découpage, transformations, prévision directe."""

import numpy as np
import pandas as pd
import pytest

from pmf.donnees import COVID, Donnees, _transformer, lire_fredmd
from pmf.modeles import ORDRE_AR, Decoupage, autoregressif, erreurs, moyenne


def _index(n=942, debut="1948-02-01"):
    return pd.date_range(debut, periods=n, freq="MS")


def _faux_chomage(n=942, graine=0):
    rng = np.random.default_rng(graine)
    return pd.Series(rng.normal(0, 0.2, n).round(1), index=_index(n), name="chomage")


def _faux_fredmd(chemin, n=200):
    dates = pd.date_range("1961-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(1)
    donnees = pd.DataFrame({
        "CLAIMSx": 300 + np.cumsum(rng.normal(0, 3, n)),
        "PAYEMS": 100_000 + np.cumsum(rng.normal(50, 20, n)),
        "INDPRO": 90 + np.cumsum(rng.normal(0.1, 0.4, n)),
    }, index=dates)
    codes = {"CLAIMSx": 5, "PAYEMS": 5, "INDPRO": 5}
    lignes = [{"sasdate": "Transform:", **codes}]
    lignes += [{"sasdate": d.strftime("%m/%d/%Y"), **r.to_dict()} for d, r in donnees.iterrows()]
    pd.DataFrame(lignes).to_csv(chemin, index=False)
    return donnees


def test_le_decoupage_retrouve_les_positions_codees_en_dur_en_2021():
    """Le carnet de 2021 écrivait 155, 803 et 864 en clair. Sur l'index réel de FRED, qui commence
    en février 1948, ces positions sont janvier 1961, janvier 2015 et février 2020."""
    index = _index()
    assert f"{index[155]:%Y-%m}" == "1961-01"
    assert f"{index[803]:%Y-%m}" == "2015-01"
    assert f"{index[864]:%Y-%m}" == COVID[0][:7]
    assert f"{index[880]:%Y-%m}" == COVID[1][:7]


def test_le_decoupage_compte_soixante_et_une_fenetres():
    serie = _faux_chomage().loc["1961-01-01":"2021-08-01"]
    d = Decoupage.depuis(serie.index, "2015-01-01", "2020-01-01")
    assert d.fenetres == 61
    assert d.debut_test == 648                      # 1961-01 à 2014-12 inclus
    assert f"{serie.index[d.debut_test]:%Y-%m}" == "2015-01"


def test_chaque_code_de_transformation_fait_ce_qu_il_annonce():
    serie = pd.Series([1.0, 2.0, 4.0, 8.0, 16.0])
    assert _transformer(serie, 1).equals(serie)
    assert _transformer(serie, 2).tolist()[1:] == [1.0, 2.0, 4.0, 8.0]
    assert np.allclose(_transformer(serie, 5).dropna(), np.log(2), atol=1e-12)
    assert np.allclose(_transformer(serie, 6).dropna(), 0.0, atol=1e-12)
    with pytest.raises(ValueError):
        _transformer(serie, 42)


def test_le_fichier_fredmd_se_lit_avec_sa_ligne_de_codes(tmp_path):
    chemin = tmp_path / "fredmd.csv"
    brut = _faux_fredmd(chemin)
    transforme = lire_fredmd(chemin)
    assert list(transforme.columns) == list(brut.columns)
    assert np.allclose(transforme["PAYEMS"].dropna(), np.log(brut["PAYEMS"]).diff().dropna(),
                       atol=1e-12)


def test_la_prevision_directe_n_utilise_que_les_retards_de_son_horizon():
    """La marque de la prévision directe : à l'horizon h, le modèle ne voit que les retards h + 1 à
    h + 4. La prévision se recompose donc à la main depuis ces quatre valeurs et les coefficients
    estimés, sans jamais faire intervenir les h mois qui précèdent immédiatement la cible."""
    from statsmodels.tsa.api import AutoReg

    serie = _faux_chomage(400, graine=2)
    d = Decoupage(debut_test=300, fenetres=10)
    for h in (0, 3, 7):
        fenetre = serie.iloc[:300]
        retards = list(range(h + 1, h + 1 + ORDRE_AR))
        ajuste = AutoReg(fenetre, lags=retards).fit()
        assert list(ajuste.model.ar_lags) == retards
        a_la_main = ajuste.params.iloc[0] + sum(
            ajuste.params.iloc[k + 1] * fenetre.iloc[-retard]
            for k, retard in enumerate(retards))
        assert autoregressif(serie, d, h=h, i=0, ordre=ORDRE_AR) == pytest.approx(a_la_main, abs=1e-10)


def test_la_fenetre_s_allonge_d_un_mois_par_tour():
    """Aucune prévision n'utilise le mois qu'elle prédit : la fenêtre s'arrête juste avant."""
    serie = _faux_chomage(400, graine=3)
    d = Decoupage(debut_test=300, fenetres=10)
    modifiee = serie.copy()
    modifiee.iloc[305] += 5.0                        # un mois postérieur à la fenêtre i = 0
    assert autoregressif(modifiee, d, h=0, i=0) == pytest.approx(
        autoregressif(serie, d, h=0, i=0), abs=1e-12)


def test_la_moyenne_historique_raccourcit_sa_fenetre_avec_l_horizon():
    """Le raccourci de 2021, conservé tel quel : la moyenne de l'horizon h s'arrête h mois plus tôt."""
    serie = _faux_chomage(400, graine=4)
    d = Decoupage(debut_test=300, fenetres=10)
    assert moyenne(serie, d, h=0, i=0) == pytest.approx(float(serie.iloc[:300].mean()))
    assert moyenne(serie, d, h=5, i=0) == pytest.approx(float(serie.iloc[:295].mean()))


def test_l_erreur_quadratique_moyenne_suit_sa_definition():
    realise = pd.Series([1.0, 2.0, 3.0])
    previsions = np.array([[1.0, 2.0, 3.0], [0.0, 2.0, 4.0]])
    assert erreurs(previsions, realise).tolist() == [0.0, pytest.approx(2 / 3)]


def test_les_donnees_savent_retirer_la_fenetre_de_la_covid():
    serie = _faux_chomage().loc["1961-01-01":"2021-08-01"]
    donnees = Donnees(serie, pd.DataFrame(index=serie.index))
    assert len(serie) == 728
    assert len(donnees.sans_covid) == 711             # 17 mois de février 2020 à juin 2021
    assert not ((donnees.sans_covid.index >= COVID[0]) & (donnees.sans_covid.index <= COVID[1])).any()
