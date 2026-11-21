"""AI output paths. Every writer must resolve the area through this module."""

from __future__ import annotations

import os
from pathlib import Path

VALID_AIS = frozenset({
    "claudetahmin",
    "geminitahmin",
    "antigravitytahmin",
    "chatgbttahmin",
    "grokbottahmin",
})

REPO_ROOT = Path(__file__).resolve().parents[2]


class QuantfootAIError(RuntimeError):
    """QUANTFOOT_AI is missing or not in the allowed set."""


def _format_valid() -> str:
    return ", ".join(sorted(VALID_AIS))


def ai_name(environ: dict[str, str] | None = None) -> str:
    """Return the configured AI folder name, or raise QuantfootAIError."""
    env = os.environ if environ is None else environ
    raw = env.get("QUANTFOOT_AI")
    name = (raw or "").strip()
    if not name:
        raise QuantfootAIError(
            "QUANTFOOT_AI tanımlı değil. Çalıştırmadan önce dışa aktarın, ör. "
            f"export QUANTFOOT_AI=grokbottahmin  (geçerli değerler: {_format_valid()})"
        )
    if name not in VALID_AIS:
        raise QuantfootAIError(
            f"QUANTFOOT_AI={name!r} geçersiz. Geçerli değerler: {_format_valid()}"
        )
    return name


def ai_area(root: Path | None = None, environ: dict[str, str] | None = None) -> Path:
    """Return tahminler/<QUANTFOOT_AI>/ under root (default: repository root)."""
    base = Path(root) if root is not None else REPO_ROOT
    return base / "tahminler" / ai_name(environ)


class LazyAiArea:
    """Path-like proxy that resolves ai_area() on first use (import stays safe).

    Joins stay lazy so ``DAILY / "takip" / "ozet.md"`` at module level does not
    require QUANTFOOT_AI until the path is actually read or written.
    """

    def __init__(self, root: Path | None = None, parts: tuple = ()) -> None:
        self._root = root
        self._parts = tuple(parts)

    def _path(self) -> Path:
        path = ai_area(self._root)
        for part in self._parts:
            path = path / part
        return path

    def __truediv__(self, other):
        return LazyAiArea(self._root, self._parts + (other,))

    def __rtruediv__(self, other):
        return Path(other) / self._path()

    def __fspath__(self) -> str:
        return str(self._path())

    def __str__(self) -> str:
        return str(self._path())

    def __repr__(self) -> str:
        try:
            return f"LazyAiArea({self._path()!r})"
        except QuantfootAIError:
            suffix = "/" + "/".join(str(p) for p in self._parts) if self._parts else ""
            return f"LazyAiArea(<QUANTFOOT_AI unset>{suffix})"

    def __eq__(self, other) -> bool:
        try:
            left = self._path()
        except QuantfootAIError:
            if isinstance(other, LazyAiArea):
                try:
                    other._path()
                except QuantfootAIError:
                    return (self._root, self._parts) == (other._root, other._parts)
            return False
        if isinstance(other, LazyAiArea):
            try:
                return left == other._path()
            except QuantfootAIError:
                return False
        return left == other

    def __hash__(self) -> int:
        try:
            return hash(self._path())
        except QuantfootAIError:
            return hash((self._root, self._parts))

    def __getattr__(self, name):
        return getattr(self._path(), name)


class LazyAiName:
    """str-like proxy for the AI folder name, resolved on use."""

    def __str__(self) -> str:
        return ai_name()

    def __repr__(self) -> str:
        try:
            return repr(ai_name())
        except QuantfootAIError:
            return "LazyAiName(<QUANTFOOT_AI unset>)"

    def __eq__(self, other) -> bool:
        return ai_name() == other

    def __hash__(self) -> int:
        return hash(ai_name())

    def __fspath__(self) -> str:
        return ai_name()

    def __add__(self, other):
        return ai_name() + other

    def __radd__(self, other):
        return other + ai_name()

    def __format__(self, spec: str) -> str:
        return format(ai_name(), spec)

    def __getattr__(self, name):
        return getattr(ai_name(), name)
