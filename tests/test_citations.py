"""Les citations du README sont-elles exactement le texte du PDF de 2021 ?

Le dépôt recopie le travail d'origine mot pour mot. Ce test lit les blocs cités du README, lit le PDF
joint, et vérifie que chaque bloc s'y retrouve. La comparaison retire tous les espaces des deux côtés :
le PDF de 2021 vient d'un traitement de texte à justification, dont l'extraction coupe des mots en
deux (« l a première », « entr e »). Ces coupures sont un artefact de mise en page, pas des mots.
L'apostrophe typographique est ramenée à l'apostrophe droite pour la même raison. La suite de lettres,
elle, doit être identique.

Une ligne de citation qui ne porte que « […] » marque une coupe dans le texte d'origine. Elle sépare
deux blocs et n'est comparée à rien, puisqu'elle ne cite rien.
"""

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
PDF = RACINE / "rapport" / "rapport_original_2021.pdf"


# l'apostrophe typographique du traitement de texte et l'apostrophe droite désignent le même mot
APOSTROPHES = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"'}

COUPURE = "[\u2026]"          # la marque d'une coupe : « […] » seul sur sa ligne


def _sans_espaces(texte: str) -> str:
    for avant, apres in APOSTROPHES.items():
        texte = texte.replace(avant, apres)
    return re.sub(r"\s+", "", texte)


def _blocs_cites(readme: str) -> list[str]:
    blocs, courant = [], []
    for ligne in readme.splitlines():
        if ligne.startswith(">"):
            contenu = ligne[1:].strip()
            if contenu and contenu != COUPURE:
                courant.append(contenu)
                continue
        if courant:
            blocs.append(" ".join(courant))
            courant = []
    if courant:
        blocs.append(" ".join(courant))
    return blocs


@pytest.fixture(scope="module")
def texte_du_pdf() -> str:
    pypdf = pytest.importorskip("pypdf")
    lecteur = pypdf.PdfReader(PDF)
    pages = [page.extract_text(extraction_mode="layout") or "" for page in lecteur.pages]
    return _sans_espaces(" ".join(pages))


def test_le_pdf_du_travail_est_bien_joint():
    assert PDF.exists(), "le rapport de 2021 doit rester dans le dépôt : les citations s'y vérifient"


def test_une_coupe_est_toujours_marquee_sur_sa_propre_ligne():
    """La marque de coupe ne se glisse jamais dans une phrase citée : elle occupe sa ligne seule."""
    lignes = (RACINE / "README.md").read_text().splitlines()
    marques = [ligne for ligne in lignes if COUPURE in ligne]
    assert marques, "les coupes entre blocs cités doivent être marquées"
    for ligne in marques:
        assert ligne.strip() == f"> {COUPURE}", f"marque de coupe mal isolée : {ligne!r}"


def test_chaque_bloc_cite_se_retrouve_mot_pour_mot(texte_du_pdf):
    blocs = _blocs_cites((RACINE / "README.md").read_text())
    assert len(blocs) >= 8, "le README doit citer le travail d'origine"
    for numero, bloc in enumerate(blocs, start=1):
        assert _sans_espaces(bloc) in texte_du_pdf, f"le bloc cité n° {numero} n'est pas dans le PDF"
