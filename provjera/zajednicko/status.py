"""Ishod jedne provjere, zajednički Word i Excel provjerama."""

from enum import Enum


class Status(Enum):
    PROSLO = "PROSLO"
    NE_PROLAZI = "NE_PROLAZI"
    NEPROVJERLJIVO = "NEPROVJERLJIVO"
