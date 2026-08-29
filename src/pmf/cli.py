"""Ligne de commande : télécharger, rejouer le hors échantillon, prolonger, dessiner."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Six modèles de prévision du chômage américain, comparés hors échantillon.")


@app.callback()
def main() -> None:
    """Sous-commandes nommées."""


@app.command()
def fetch() -> None:
    """Le chômage de FRED et la base FRED-MD, écrits dans `data/raw/`."""
    from pmf import donnees

    for cle, chemin in donnees.fetch().items():
        typer.echo(f"{cle:10s} {chemin} ({chemin.stat().st_size / 1e6:.2f} Mo)")


@app.command()
def bases(out: Path = Path("results")) -> None:
    """La taille des deux séries et le découpage, sans rien estimer."""
    import pandas as pd

    from pmf import donnees
    from pmf.modeles import Decoupage

    d = donnees.charger()
    dec = Decoupage.depuis(d.chomage.index, donnees.DEBUT_TEST, donnees.FIN_TEST)
    table = pd.DataFrame([{
        "mois": len(d.chomage), "premier": f"{d.chomage.index[0]:%Y-%m}",
        "dernier": f"{d.chomage.index[-1]:%Y-%m}", "series_fredmd": d.fredmd.shape[1],
        "apprentissage": dec.debut_test, "fenetres_de_test": dec.fenetres,
        "mois_sans_covid": len(d.sans_covid),
    }])
    (out / "tables").mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "tables" / "dimensions.csv", index=False)
    typer.echo(table.T.to_string(header=False))


@app.command()
def lab(out: Path = Path("results"), modeles: str = "", horizons: int = 12) -> None:
    """Les six modèles en pseudo hors échantillon, puis la table des erreurs relatives."""
    import time

    import pandas as pd

    from pmf import donnees
    from pmf import modeles as mod
    from pmf.modeles import Decoupage

    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    d = donnees.charger()
    dec = Decoupage.depuis(d.chomage.index, donnees.DEBUT_TEST, donnees.FIN_TEST)
    realise = d.chomage.iloc[dec.debut_test : dec.debut_test + dec.fenetres]
    choisis = [m.strip() for m in modeles.split(",") if m.strip()] or mod.ORDRE_MODELES

    eqm, durees = {}, {}
    for cle in choisis:
        depart = time.perf_counter()
        previsions = mod.prevoir(cle, d, dec, horizons=horizons)
        eqm[cle] = mod.erreurs(previsions, realise)
        durees[cle] = round(time.perf_counter() - depart, 1)
        pd.DataFrame(previsions.T, index=realise.index,
                     columns=[f"h{h + 1}" for h in range(horizons)]).to_csv(
            tables / f"previsions_{cle}.csv")
        typer.echo(f"{mod.LIBELLES[cle]:34s} EQM h1 {eqm[cle][0]:.6f}  ({durees[cle]:6.1f} s)")

    table = pd.DataFrame(eqm, index=[f"h{h + 1}" for h in range(horizons)])
    table.to_csv(tables / "eqm_absolu.csv")
    if "ar1" in table.columns:
        (table / table.loc["h1", "ar1"]).to_csv(tables / "eqm_relatif.csv")
    pd.Series(durees, name="secondes").to_csv(tables / "durees.csv")


@app.command()
def futur(out: Path = Path("results")) -> None:
    """Les prévisions de 2021-09 à 2022-09, avec et sans la Covid, contre le chômage réalisé."""
    from pmf import donnees
    from pmf import futur as fut

    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    d = donnees.charger()
    previsions = fut.prevoir(d)
    previsions.to_csv(tables / "previsions_2021_2022.csv")

    realise = donnees.charger_chomage(fin=None)
    verdict = fut.confronter(previsions, realise)
    verdict.to_csv(tables / "verdict_2022.csv", index=False)
    typer.echo(verdict.to_string(index=False))


@app.command()
def figures(out: Path = Path("results")) -> None:
    """Les figures, reconstruites depuis les tables de `results/tables/`."""
    from pmf import figures as fig

    for chemin in fig.toutes(out):
        typer.echo(f"écrit {chemin}")


if __name__ == "__main__":
    app()
