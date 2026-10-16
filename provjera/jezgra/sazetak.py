"""Sažetak provjere za preuzimanje (FR-12, AD-10): samostalan HTML bez sadržaja rada.

U sažetak ulazi samo status po pravilu, nikad očekivane ili pronađene vrijednosti,
isječci ni naziv datoteke. Vrijeme provjere predaje pozivatelj, jer jezgra ne čita sat.
"""

from html import escape

from provjera.jezgra.nalaz import Izvjestaj
from provjera.jezgra.poruke import poruka
from provjera.jezgra.pravila import REGISTAR
from provjera.jezgra.provjera import spremnost, status_pravila

_STIL = """
body { font-family: system-ui, sans-serif; max-width: 42rem; margin: 2rem auto;
       padding: 0 1rem; color: #1a1a1a; }
h1 { font-size: 1.4rem; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: .25rem 1rem; }
dt { font-weight: 600; }
table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
th, td { border: 1px solid #ccc; padding: .4rem .6rem; text-align: left; }
.ukupno { font-weight: 600; margin-top: 1rem; }
.napomena { color: #555; font-size: .9rem; margin-top: 1.5rem; }
"""


def html_sazetka(izvjestaj: Izvjestaj, naziv_vjezbe: str, vrijeme: str) -> str:
    redci = "".join(
        f"<tr><td>{escape(poruka(f'pravilo.{pravilo_id}'))}</td>"
        f"<td>{escape(poruka(f'status.{status.value}'))}</td></tr>"
        for pravilo_id in REGISTAR
        if (status := status_pravila(izvjestaj.nalazi, pravilo_id)) is not None
    )
    ukupno = "sazetak.spremno" if spremnost(izvjestaj) else "sazetak.nije_spremno"
    # Uz fiksne margine student ne upisuje Rbr., pa ga sažetak ne navodi.
    polja = (() if izvjestaj.rbr is None else (("sazetak.rbr", str(izvjestaj.rbr)),)) + (
        ("sazetak.vjezba", naziv_vjezbe),
        ("sazetak.verzija", izvjestaj.profil_verzija),
        ("sazetak.vrijeme", vrijeme),
    )
    opis = "".join(f"<dt>{escape(poruka(k))}</dt><dd>{escape(v)}</dd>" for k, v in polja)
    return (
        '<!doctype html>\n<html lang="hr">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(poruka('sazetak.naslov'))}</title>\n<style>{_STIL}</style>\n"
        "</head>\n<body>\n"
        f"<h1>{escape(poruka('sazetak.naslov'))}</h1>\n<dl>{opis}</dl>\n"
        f'<p class="ukupno">{escape(poruka(ukupno))}</p>\n'
        f"<table><thead><tr><th scope=\"col\">{escape(poruka('sazetak.stupac_pravilo'))}</th>"
        f"<th scope=\"col\">{escape(poruka('sazetak.stupac_status'))}</th></tr></thead>"
        f"<tbody>{redci}</tbody></table>\n"
        f'<p class="napomena">{escape(poruka("sazetak.napomena"))}</p>\n'
        "</body>\n</html>\n"
    )
