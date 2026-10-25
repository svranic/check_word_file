"""Referentna rješenja obrazaca: formule koje nastavnik može upisati u predložak.

Služe za provjeru predloška i provjere (rješenje mora proći sve provjere) i kao
nastavnikov primjer. Pomoćni izračuni su u stupcima N–R (slobodno područje).
"""


def _dms(redak: int, stupac0: str, sekunde: str, predznak: str | None = None) -> dict[str, str]:
    """Formule °, ′, ″ iz ćelije s ukupnim (nenegativnim) brojem sekundi."""
    s = ord(stupac0)
    formule = {
        f"{chr(s)}{redak}": f"=INT({sekunde}/3600)",
        f"{chr(s + 1)}{redak}": f"=INT(MOD({sekunde},3600)/60)",
        f"{chr(s + 2)}{redak}": f"=MOD({sekunde},60)",
    }
    if predznak:
        formule[predznak[0]] = predznak[1]
    return formule


def _sinus() -> dict[str, str]:
    f = {
        "M8": "α dec.", "M9": "β dec.", "M10": "γ dec.", "M11": "Σ dec.",
        "N7": "mjereno (°)", "O7": "izjednačeno (°)", "P7": "Σ″ mjereno", "Q7": "Σ″ izjednačeno",
        "R7": "popravak (″)",
    }
    # Popravci u cijelim sekundama: prva dva kuta ROUND(f/3), treći ostatak do f.
    f["R8"] = "=ROUND($E$12/3,0)"
    f["R9"] = "=ROUND($E$12/3,0)"
    f["R10"] = "=$E$12-R8-R9"
    for r, (st, mi, se) in zip((8, 9, 10), (("C8", "D8", "E8"), ("C9", "D9", "E9"), ("C10", "D10", "E10"))):
        f[f"N{r}"] = f"={st}+{mi}/60+{se}/3600"
        f[f"O{r}"] = f"=N{r}+R{r}/3600"
        f[f"Q{r}"] = f"=ROUND(O{r}*3600,2)"
        f.update(_dms(r, "F", f"Q{r}"))
        f[f"I{r}"] = f"=SIN(RADIANS(O{r}))"
    f["N11"] = "=SUM(N8:N10)"
    f["O11"] = "=SUM(O8:O10)"
    f["P11"] = "=ROUND(N11*3600,2)"
    f["Q11"] = "=ROUND(O11*3600,2)"
    f.update(_dms(11, "C", "P11"))
    f.update(_dms(11, "F", "Q11"))
    f["E12"] = "=(180-N11)*3600"
    f["E13"] = "=E12/3"
    f["I12"] = "=K8/I8"
    f["K9"] = "=I12*I9"
    f["K10"] = "=I12*I10"
    f["J12"] = "=K9*COS(RADIANS(O10))"
    f["J13"] = "=K10*COS(RADIANS(O9))"
    f["K13"] = "=J12+J13"
    return f


def _kosinus() -> dict[str, str]:
    f = {"M8": "α dec.", "M9": "β dec.", "M10": "γ dec.", "M11": "Σ dec.", "N7": "°", "O7": "″ ukupno"}
    f["N8"] = "=C8+D8/60+E8/3600"
    f["J8"] = "=G8^2"
    f["J9"] = "=G9^2"
    f["J10"] = "=COS(RADIANS(N8))"
    f["J11"] = "=2*G8*G9*J10"
    f["J12"] = "=J8+J9-J11"
    f["J13"] = "=SQRT(J12)"
    f["J14"] = "=(J12+J9-J8)/(2*J13*G9)"
    f["J15"] = "=(J12+J8-J9)/(2*J13*G8)"
    f["N9"] = "=DEGREES(ACOS(J14))"
    f["N10"] = "=DEGREES(ACOS(J15))"
    f["N11"] = "=N8+N9+N10"
    for r in (9, 10, 11):
        f[f"O{r}"] = f"=ROUND(N{r}*3600,2)"
        f.update(_dms(r, "C", f"O{r}"))
    f["G13"] = "=G8/SIN(RADIANS(N9))*SIN(RADIANS(N8))"
    f["G14"] = "=G9/SIN(RADIANS(N10))*SIN(RADIANS(N8))"
    return f


def _tangens() -> dict[str, str]:
    f = {
        "M8": "α dec.", "M9": "β dec.", "M10": "γ dec.", "M11": "Σ dec.",
        "M12": "(β+γ)/2 dec.", "M13": "(β−γ)/2 dec.", "N7": "°", "O7": "|″| ukupno",
    }
    f["N8"] = "=D8+E8/60+F8/3600"
    f["K8"] = "=N8/2"
    f["K9"] = "=1/TAN(RADIANS(K8))"
    f["K10"] = "=H8-H9"
    f["K11"] = "=H8+H9"
    f["K12"] = "=K10/K11"
    f["K13"] = "=DEGREES(ATAN(K12*K9))"
    f["N12"] = "=90-K8"
    f["N13"] = "=K13"
    f["N9"] = "=N12+N13"
    f["N10"] = "=N12-N13"
    f["N11"] = "=N8+N9+N10"
    for r in (9, 10, 11, 12, 13):
        f[f"O{r}"] = f"=ROUND(ABS(N{r})*3600,2)"
        predznak = ("C13", '=IF(N13<0,"-","+")') if r == 13 else None
        f.update(_dms(r, "D", f"O{r}", predznak))
    f["H10"] = "=SQRT(H8^2+H9^2-2*H8*H9*COS(RADIANS(N8)))"
    f["H13"] = "=H8/SIN(RADIANS(N9))*SIN(RADIANS(N8))"
    return f


RJESENJA = {"sinus": _sinus, "kosinus": _kosinus, "tangens": _tangens}
