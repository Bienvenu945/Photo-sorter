"""Filtres de la file de tri : mini-langage `:commande args`, extensible par un simple décorateur.

Syntaxe
-------
    :date 2026-08 :portrait        ET implicite entre les termes
    :portrait | :carre             OU (groupes séparés par « | »)
    -:grand                        NON (préfixe « - »)
    :camera "Canon EOS"            guillemets pour les arguments avec espaces
    :toutes                        retire tous les filtres précédents

Ajouter un filtre = une fonction décorée :

    @command("noir", help="Photos très sombres")
    def _noir(args, ctx):
        return lambda meta: ...
"""
from __future__ import annotations

import calendar
import difflib
import re
import shlex
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from services.date_extractor import PhotoMeta

Predicate = Callable[[PhotoMeta], bool]
Factory = Callable[[list[str], "FilterContext"], Predicate]


class FilterError(ValueError):
    """Commande de filtre invalide (message lisible par l'utilisateur)."""


@dataclass(frozen=True)
class FilterContext:
    now: datetime = field(default_factory=datetime.now)
    big_bytes: int = 5 * 1024 * 1024
    small_bytes: int = 500 * 1024
    recent_days: int = 7


@dataclass(frozen=True)
class Command:
    name: str
    factory: Factory
    help: str
    usage: str


_COMMANDS: dict[str, Command] = {}


def command(name: str, help: str = "", usage: str = "") -> Callable[[Factory], Factory]:
    """Enregistre une commande de filtre."""
    def deco(fn: Factory) -> Factory:
        _COMMANDS[name] = Command(name, fn, help, usage or f":{name}")
        return fn
    return deco


def commands() -> list[Command]:
    return [_COMMANDS[k] for k in sorted(_COMMANDS)]


def suggest(prefix: str) -> list[str]:
    """Autocomplétion : noms de commandes (avec « : ») commençant par ``prefix``."""
    p = prefix.lstrip("-:").lower()
    return [f":{n}" for n in sorted(_COMMANDS) if n.startswith(p)]


# ---------------------------------------------------------------- utilitaires d'arguments
_SIZE_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(k|ko|kb|m|mo|mb|g|go|gb|o|b)?$", re.I)
_UNITS = {"": 1, "o": 1, "b": 1, "k": 1024, "ko": 1024, "kb": 1024, "m": 1024**2, "mo": 1024**2, "mb": 1024**2,
          "g": 1024**3, "go": 1024**3, "gb": 1024**3}


def parse_size(text: str) -> int:
    """'5MB', '500ko', '2.5 Mo' -> octets."""
    m = _SIZE_RE.match(text.strip())
    if not m:
        raise FilterError(f"Taille invalide : « {text} » (exemples : 5MB, 500ko)")
    return int(float(m.group(1).replace(",", ".")) * _UNITS[(m.group(2) or "").lower()])


def _period(text: str) -> tuple[date, date]:
    """'2026' / '2026-08' / '2026-08-15' -> (premier jour, dernier jour)."""
    try:
        parts = [int(p) for p in text.split("-")]
        if len(parts) == 1:
            return date(parts[0], 1, 1), date(parts[0], 12, 31)
        if len(parts) == 2:
            return date(parts[0], parts[1], 1), date(parts[0], parts[1], calendar.monthrange(*parts)[1])
        if len(parts) == 3:
            d = date(*parts)
            return d, d
    except (ValueError, TypeError):
        pass
    raise FilterError(f"Date invalide : « {text} » (formats : AAAA-MM, AAAA-MM-JJ, >AAAA-MM-JJ, <AAAA-MM-JJ)")


# ---------------------------------------------------------------- commandes
@command("date", "Filtre par date de prise de vue", ":date 2026-08 | :date >2026-08-15 | :date <2020-01-01")
def _date(args, ctx):
    if len(args) != 1:
        raise FilterError("Usage : :date AAAA-MM, AAAA-MM-JJ, >AAAA-MM-JJ ou <AAAA-MM-JJ")
    arg = args[0]
    if arg[0] == ">":
        end = _period(arg[1:])[1]
        return lambda m: m.date.date() > end
    if arg[0] == "<":
        start = _period(arg[1:])[0]
        return lambda m: m.date.date() < start
    start, end = _period(arg)
    return lambda m: start <= m.date.date() <= end


def _orientation(name: str, label: str) -> None:
    @command(name, f"Format {label} uniquement")
    def _f(args, ctx, _n=name):
        return lambda m: m.orientation == _n


for _n, _l in (("portrait", "portrait"), ("paysage", "paysage"), ("carre", "carré")):
    _orientation(_n, _l)


@command("grand", "Fichiers plus gros que le seuil (5 Mo)", ":grand [10MB]")
def _grand(args, ctx):
    limit = parse_size(args[0]) if args else ctx.big_bytes
    return lambda m: m.size_bytes > limit


@command("petit", "Fichiers plus petits que le seuil (500 Ko)", ":petit [200ko]")
def _petit(args, ctx):
    limit = parse_size(args[0]) if args else ctx.small_bytes
    return lambda m: m.size_bytes < limit


@command("nouveau", "Ajoutés aujourd'hui")
def _nouveau(args, ctx):
    today = ctx.now.date()
    return lambda m: m.added.date() == today


@command("recent", "Ajoutés ces 7 derniers jours", ":recent [jours]")
def _recent(args, ctx):
    try:
        days = int(args[0]) if args else ctx.recent_days
    except ValueError:
        raise FilterError("Usage : :recent [nombre de jours]") from None
    limit = ctx.now - timedelta(days=days)
    return lambda m: m.added >= limit


@command("camera", "Appareil photo (contient, sans casse)", ":camera CANON")
def _camera(args, ctx):
    if not args:
        raise FilterError("Usage : :camera NOM (ex. :camera canon)")
    needle = " ".join(args).lower()
    return lambda m: bool(m.camera) and needle in m.camera.lower()


@command("toutes", "Retire tous les filtres")
def _toutes(args, ctx):
    return lambda m: True


# ---------------------------------------------------------------- filtre composé
@dataclass(frozen=True)
class Term:
    name: str
    args: tuple[str, ...]
    negated: bool
    predicate: Predicate

    def matches(self, meta: PhotoMeta) -> bool:
        return self.predicate(meta) != self.negated

    def describe(self) -> str:
        return ("NON " if self.negated else "") + " ".join((self.name, *self.args))


@dataclass(frozen=True)
class Filter:
    """OU de groupes, chaque groupe étant un ET de termes. Un filtre vide laisse tout passer."""
    groups: tuple[tuple[Term, ...], ...] = ()

    @property
    def is_empty(self) -> bool:
        return not any(self.groups)

    def matches(self, meta: PhotoMeta) -> bool:
        if self.is_empty:
            return True
        return any(all(t.matches(meta) for t in g) for g in self.groups if g)

    def apply(self, items: Iterable[PhotoMeta]) -> list[PhotoMeta]:
        return [m for m in items if self.matches(m)]

    def describe(self) -> str:
        if self.is_empty:
            return "aucun filtre"
        return "  OU  ".join(" ET ".join(t.describe() for t in g) for g in self.groups if g)


def parse(text: str, ctx: FilterContext | None = None) -> Filter:
    """Analyse une commande de filtre. Lève ``FilterError`` avec un message explicite."""
    ctx = ctx or FilterContext()
    try:
        tokens = shlex.split(text.strip())
    except ValueError as e:
        raise FilterError(f"Guillemets mal fermés : {e}") from e
    groups: list[list[Term]] = [[]]
    pending: tuple[str, bool] | None = None
    args: list[str] = []

    def flush() -> None:
        nonlocal pending, args
        if pending is None:
            return
        name, neg = pending
        if name == "toutes":
            groups[:] = [[]]
        else:
            groups[-1].append(Term(name, tuple(args), neg, _COMMANDS[name].factory(list(args), ctx)))
        pending, args = None, []

    for tok in tokens:
        neg = tok.startswith("-:")
        if tok.startswith(":") or neg:
            flush()
            name = tok.lstrip("-:").lower()
            if name not in _COMMANDS:
                close = difflib.get_close_matches(name, _COMMANDS, n=1)
                hint = f" Vouliez-vous dire :{close[0]} ?" if close else ""
                raise FilterError(f"Commande inconnue : :{name}.{hint}")
            pending = (name, neg)
        elif tok == "|":
            flush()
            groups.append([])
        elif pending is None:
            raise FilterError(f"Argument sans commande : « {tok} » (une commande commence par « : »)")
        else:
            args.append(tok)
    flush()
    return Filter(tuple(tuple(g) for g in groups if g))


def complete(text: str) -> str:
    """Complète la dernière commande du texte (touche Tab).

    Une seule possibilité -> mot complet suivi d'un espace ; plusieurs -> leur préfixe commun ; aucune -> inchangé.
    """
    if not text or text[-1].isspace():
        return text
    head, _, last = text.rpartition(" ")
    if not (last.startswith(":") or last.startswith("-:")):
        return text
    options = suggest(last)
    if not options:
        return text
    common = options[0]
    for opt in options[1:]:
        n = 0
        while n < min(len(common), len(opt)) and common[n] == opt[n]:
            n += 1
        common = common[:n]
    done = ("-" if last.startswith("-") else "") + common + (" " if len(options) == 1 else "")
    return (head + " " if head else "") + done
