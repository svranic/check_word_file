"""PDF sa svojstvima za objavu u e-učenju (priča 3.5): fpdf2 i DejaVuSans.

Adapter samo raspoređuje sadržaj na stranicu: retci i zajednički zahtjevi dolaze iz
``jezgra.svojstva`` (margine iz ``formula.margine``, nazivi iz ``naziv.kanonski``),
a svi tekstovi iz ``poruke`` (``pdf.*``). U PDF ne ulaze JMBAG-ovi ni neaktivni studenti.
"""

from collections.abc import Iterable
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from provjera.adapteri.popis import zapisi_atomski
from provjera.jezgra import profil as profil_modul
from provjera.jezgra import svojstva
from provjera.jezgra.poruke import poruka
from provjera.jezgra.profil import Profil

FONTOVI = Path(__file__).resolve().parents[1] / "resursi" / "fontovi"
FONT = "DejaVuSans"
VELICINA = 10
VELICINA_TABLICE = 9
VELICINA_NASLOVA = 16
VELICINA_PODNASLOVA = 12
RAZMAK = 2  # mm između odlomaka
# Relativne širine stupaca: Rbr., ime, prezime, naziv datoteke, četiri margine.
SIRINE_STUPACA = (10, 26, 30, 72, 15, 15, 15, 15)
STUPCI = ("rbr", "ime", "prezime", "naziv", "gore", "dolje", "lijevo", "desno")
PORAVNANJE = ("RIGHT", "LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT")
# Uz fiksne margine tablica ima samo prva četiri stupca (margine su u zajedničkim zahtjevima).
STUPACA_BEZ_MARGINA = 4


class _Dokument(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(FONT, size=8)
        self.cell(
            0,
            8,
            poruka("pdf.stranica", broj=self.page_no(), ukupno=self.str_alias_nb_pages),
            align="C",
        )


def _novi_dokument(profil: Profil) -> _Dokument:
    pdf = _Dokument(orientation="L", unit="mm", format="A4")
    pdf.add_font(FONT, style="", fname=FONTOVI / "DejaVuSans.ttf")
    pdf.add_font(FONT, style="B", fname=FONTOVI / "DejaVuSans-Bold.ttf")
    pdf.set_title(poruka("pdf.naslov", naziv=profil.vjezba.naziv))
    pdf.set_creator(poruka("nastavnik.naslov"))
    pdf.set_lang("hr")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    return pdf


def _odlomak(pdf: FPDF, tekst: str, *, velicina: int = VELICINA, podebljano: bool = False,
             poveznica: str = "") -> None:
    pdf.set_font(FONT, style="B" if podebljano else "", size=velicina)
    pdf.multi_cell(0, velicina * 0.5, tekst, link=poveznica, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(RAZMAK)


def izradi_pdf(profil: Profil, studenti: Iterable[svojstva.StudentPopisa]) -> bytes:
    """PDF iz zamrznutog popisa i profila; Rbr. izvan formule baca ``ValueError``."""
    retci = svojstva.retci(profil, studenti)
    pdf = _novi_dokument(profil)

    _odlomak(pdf, poruka("pdf.naslov", naziv=profil.vjezba.naziv),
             velicina=VELICINA_NASLOVA, podebljano=True)
    _odlomak(pdf, poruka("pdf.verzija", verzija=profil_modul.verzija(profil)))
    _odlomak(pdf, poruka("pdf.poveznica", poveznica=profil.vjezba.poveznica),
             poveznica=profil.vjezba.poveznica)
    fiksne = profil.formula.fiksne_margine
    _odlomak(pdf, poruka("pdf.uputa_fiksne" if fiksne else "pdf.uputa"))
    _odlomak(pdf, poruka("pdf.privatnost", obrada=poruka("privatnost.obrada")))

    zahtjevi = svojstva.zajednicki_zahtjevi(profil)
    if zahtjevi:
        _odlomak(pdf, poruka("pdf.zajednicki_naslov"),
                 velicina=VELICINA_PODNASLOVA, podebljano=True)
        pdf.set_font(FONT, size=VELICINA)
        for zahtjev in zahtjevi:
            pdf.multi_cell(0, VELICINA * 0.5, poruka("pdf.stavka", zahtjev=zahtjev), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(RAZMAK)

    broj_stupaca = STUPACA_BEZ_MARGINA if fiksne else len(STUPCI)
    stupci = STUPCI[:broj_stupaca]
    _odlomak(pdf, poruka("pdf.tablica_naslov_fiksne" if fiksne else "pdf.tablica_naslov"),
             velicina=VELICINA_PODNASLOVA, podebljano=True)
    if not fiksne:
        _odlomak(pdf, poruka("pdf.tablica_opis"))
    pdf.set_font(FONT, size=VELICINA_TABLICE)
    with pdf.table(
        col_widths=SIRINE_STUPACA[:broj_stupaca],
        text_align=PORAVNANJE[:broj_stupaca],
        headings_style=FontFace(emphasis="BOLD"),
        repeat_headings=1,
        line_height=VELICINA_TABLICE * 0.5,
    ) as tablica:
        tablica.row([poruka(f"pdf.stupac_{stupac}") for stupac in stupci])
        for redak in retci:
            tablica.row([str(getattr(redak, stupac)) for stupac in stupci])
    return bytes(pdf.output())


def spremi_pdf(sadrzaj: bytes, putanja: Path) -> Path:
    """Atomski zapisuje (i prepisuje) PDF."""
    zapisi_atomski(putanja, sadrzaj)
    return putanja
