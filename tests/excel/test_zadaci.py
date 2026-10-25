import pytest

from provjera.excel.jezgra.zadaci import (
    ZADACI,
    dms_u_stupnjeve,
    kontrolni_podaci,
    osobni_podaci,
    stupnjevi_u_dms,
)


def ulazi_sinus(alfa, beta, gama, a):
    u = {}
    for k, (st, mi, se) in zip(("alfa", "beta", "gama"), (alfa, beta, gama)):
        u[f"{k}_st"], u[f"{k}_min"], u[f"{k}_sek"] = st, mi, se
    u["a"] = a
    return u


def test_sinus_odgovara_primjeru_iz_obrasca():
    # Primjer s obrasca 13: 70°33′29″, 60°25′27″, 49°01′28″, a = 155,65
    r = ZADACI["sinus"].izracun(ulazi_sinus((70, 33, 29), (60, 25, 27), (49, 1, 28), 155.65))
    assert r["f"] == pytest.approx(-24)
    assert r["v"] == pytest.approx(-8)
    assert r["sin_alfa"] == pytest.approx(0.94297, abs=1e-5)
    assert r["m"] == pytest.approx(165.06, abs=0.01)
    assert r["b"] == pytest.approx(143.55, abs=0.01)
    assert r["c"] == pytest.approx(124.62, abs=0.01)
    assert r["a_kontrola"] == pytest.approx(155.65, abs=0.01)


def test_kosinus_odgovara_primjeru_iz_obrasca():
    u = {"alfa_st": 59, "alfa_min": 28, "alfa_sek": 52, "b": 220.65, "c": 214.49}
    r = ZADACI["kosinus"].izracun(u)
    assert r["a"] == pytest.approx(215.93, abs=0.005)
    assert r["beta"] == pytest.approx(dms_u_stupnjeve(61, 40, 44), abs=1 / 3600)
    assert r["gama"] == pytest.approx(dms_u_stupnjeve(58, 50, 24), abs=1 / 3600)
    assert r["zbroj"] == pytest.approx(180)


def test_tangens_odgovara_primjeru_iz_obrasca():
    u = {"alfa_st": 58, "alfa_min": 27, "alfa_sek": 48, "b": 211.65, "c": 209.48}
    r = ZADACI["tangens"].izracun(u)
    assert r["cot_pola"] == pytest.approx(1.786969465, abs=1e-8)
    assert r["arctan"] == pytest.approx(0.5275590, abs=1e-6)
    assert r["a"] == pytest.approx(205.664, abs=0.001)
    assert r["beta"] == pytest.approx(dms_u_stupnjeve(61, 17, 45), abs=1 / 3600)
    assert r["gama"] == pytest.approx(dms_u_stupnjeve(60, 14, 27), abs=1 / 3600)


def test_kosinus_i_tangens_daju_isti_trokut():
    u = {"alfa_st": 47, "alfa_min": 10, "alfa_sek": 5, "b": 130.2, "c": 188.9}
    cos, tan = ZADACI["kosinus"].izracun(u), ZADACI["tangens"].izracun(u)
    for k in ("a", "beta", "gama"):
        assert cos[k] == pytest.approx(tan[k])


@pytest.mark.parametrize("kut", [0.0, 12.5, 59.99999, -0.5, -12.5])
def test_dms_povratno(kut):
    st, mi, se = stupnjevi_u_dms(kut)
    znak = -1 if kut < 0 else 1
    assert znak * dms_u_stupnjeve(abs(st), abs(mi), abs(se)) == pytest.approx(kut, abs=0.5 / 3600)


@pytest.mark.parametrize("zadatak", list(ZADACI.values()), ids=list(ZADACI))
def test_osobni_podaci_su_ponovljivi_i_razliciti(zadatak):
    a = osobni_podaci(zadatak, 1, "0036000001")
    assert a == osobni_podaci(zadatak, 1, "0036000001")
    assert a != osobni_podaci(zadatak, 1, "0036000002")
    assert a != osobni_podaci(zadatak, 2, "0036000001")


def test_sinus_generator_ima_zatvaranje_oba_predznaka():
    zatvaranja = [ZADACI["sinus"].izracun(u)["f"] for u in kontrolni_podaci(ZADACI["sinus"])]
    assert all(round(f) != 0 and abs(f - round(f)) < 1e-6 for f in zatvaranja)
    assert any(f > 0 for f in zatvaranja) and any(f < 0 for f in zatvaranja)


@pytest.mark.parametrize("korak", [1, 10])
def test_kontrolni_podaci_sinusa_imaju_zatvaranje_s_oba_ostatka(korak):
    # Raspored popravaka mora se provjeriti i za |f| mod 3 = 1 i za |f| mod 3 = 2.
    zatvaranja = [round(ZADACI["sinus"].izracun(u)["f"]) for u in kontrolni_podaci(ZADACI["sinus"], korak)]
    assert {(f > 0, abs(f) % 3) for f in zatvaranja} == {(True, 1), (False, 1), (True, 2), (False, 2)}


@pytest.mark.parametrize("zadatak", list(ZADACI.values()), ids=list(ZADACI))
def test_mjereni_kutovi_su_visekratnici_koraka(zadatak):
    for i in range(100):
        u = osobni_podaci(zadatak, i, "x", korak=10)
        assert all(u[f"{k}_sek"] % 10 == 0 for k in zadatak.kutovi_ulaza)


def test_sinus_zatvaranje_je_realno_za_korak_10():
    for i in range(200):
        f = ZADACI["sinus"].izracun(osobni_podaci(ZADACI["sinus"], i, "x", korak=10))["f"]
        assert round(f) % 10 == 0 and 0 < abs(f) <= 90


@pytest.mark.parametrize("zadatak", ["kosinus", "tangens"])
def test_kontrolni_podaci_imaju_b_vece_i_manje_od_c(zadatak):
    podaci = kontrolni_podaci(ZADACI[zadatak])
    assert any(u["b"] > u["c"] for u in podaci) and any(u["b"] < u["c"] for u in podaci)


@pytest.mark.parametrize("zadatak", list(ZADACI.values()), ids=list(ZADACI))
def test_generirani_podaci_su_valjani(zadatak):
    for i in range(200):
        u = osobni_podaci(zadatak, i, "x")
        for k in zadatak.kutovi_ulaza:
            assert 0 <= u[f"{k}_min"] < 60 and 0 <= u[f"{k}_sek"] < 60
        r = zadatak.izracun(u)
        assert all(v == v for v in r.values())  # bez NaN
