"""
Convert LaTeX math notation into readable plain (Unicode) text.

The generation model often emits equations wrapped in LaTeX delimiters, e.g.

    \\[ P(\\text{HT}) = \\frac{1}{4} \\]

which is meaningless to a lay reader and to our PDF/DOCX renderers. This module
turns that into normal text like ``P(HT) = 1/4`` while preserving meaning.

The goal is NOT typeset math — it is faithful, readable plain text that works
identically on screen and in downloads. A mirror implementation lives in
``frontend/src/utils/latexToText.js``; keep the two rule tables in sync.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Symbol tables
# ---------------------------------------------------------------------------

# LaTeX command name -> Unicode replacement. Matched as ``\name`` with a word
# boundary so ``\int`` does not clobber ``\intercal`` etc.
_SYMBOLS = {
    # Greek (lowercase)
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "θ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "varpi": "π", "rho": "ρ", "varrho": "ρ", "sigma": "σ",
    "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω",
    # Greek (uppercase)
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    # Binary / relational operators
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓", "ast": "∗",
    "star": "⋆", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠",
    "ne": "≠", "approx": "≈", "equiv": "≡", "sim": "∼", "simeq": "≃",
    "cong": "≅", "propto": "∝", "ll": "≪", "gg": "≫",
    # Set / logic
    "in": "∈", "notin": "∉", "ni": "∋", "subset": "⊂", "subseteq": "⊆",
    "supset": "⊃", "supseteq": "⊇", "cup": "∪", "cap": "∩", "emptyset": "∅",
    "varnothing": "∅", "setminus": "\\", "forall": "∀", "exists": "∃",
    "nexists": "∄", "neg": "¬", "lnot": "¬", "land": "∧", "wedge": "∧",
    "lor": "∨", "vee": "∨", "oplus": "⊕", "otimes": "⊗",
    # Big operators
    "sum": "Σ", "prod": "∏", "int": "∫", "iint": "∬", "iiint": "∭",
    "oint": "∮", "coprod": "∐", "bigcup": "⋃", "bigcap": "⋂",
    # Calculus / misc
    "partial": "∂", "nabla": "∇", "infty": "∞", "aleph": "ℵ", "hbar": "ℏ",
    "ell": "ℓ", "Re": "ℜ", "Im": "ℑ", "wp": "℘", "angle": "∠",
    "perp": "⊥", "parallel": "∥", "therefore": "∴", "because": "∵",
    "prime": "′",
    # Arrows
    "rightarrow": "→", "to": "→", "gets": "←", "leftarrow": "←",
    "leftrightarrow": "↔", "Rightarrow": "⇒", "implies": "⇒",
    "Leftarrow": "⇐", "Leftrightarrow": "⇔", "iff": "⇔", "mapsto": "↦",
    "uparrow": "↑", "downarrow": "↓",
    # Dots
    "ldots": "…", "cdots": "…", "dots": "…", "vdots": "⋮", "ddots": "⋱",
    # Misc letters / constants
    "deg": "°", "circ": "°", "bmod": "mod", "pmod": "mod",
}

# Superscript / subscript character maps (used when the whole exponent maps).
_SUP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
    "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "−": "⁻", "=": "⁼",
    "(": "⁽", ")": "⁾", "n": "ⁿ", "i": "ⁱ", "a": "ᵃ", "b": "ᵇ", "c": "ᶜ",
    "d": "ᵈ", "e": "ᵉ", "x": "ˣ", "y": "ʸ",
}
_SUB = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
    "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "−": "₋", "=": "₌",
    "(": "₍", ")": "₎", "a": "ₐ", "e": "ₑ", "i": "ᵢ", "j": "ⱼ", "n": "ₙ",
    "o": "ₒ", "x": "ₓ",
}

# Font/formatting wrappers whose braces we simply unwrap, keeping the content.
_UNWRAP_CMDS = (
    "text", "textrm", "textbf", "textit", "textsf", "texttt", "mathrm",
    "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathbb", "mathfrak",
    "operatorname", "boldsymbol", "bm", "mbox", "hbox",
)

# Spacing / no-op commands -> a single space (or nothing).
_SPACING = {
    "quad": " ", "qquad": "  ", "thinspace": " ", "medspace": " ",
    "thickspace": " ", "enspace": " ", "space": " ", "!": "",
}

# ---------------------------------------------------------------------------
# Balanced-brace helpers
# ---------------------------------------------------------------------------

_CMD_RE = re.compile(r"\\([a-zA-Z]+)")


def _read_group(s: str, i: int):
    """If s[i] == '{', return (inner_content, index_after_matching_brace)."""
    if i >= len(s) or s[i] != "{":
        return None, i
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return None, i  # unbalanced; treat as literal


def _wrap(expr: str) -> str:
    """Parenthesize a fraction operand only when needed to keep meaning."""
    expr = expr.strip()
    if len(expr) <= 1:
        return expr
    if expr.startswith("(") and expr.endswith(")"):
        return expr
    if re.search(r"[+\-−×÷/=<>±\s]", expr):
        return f"({expr})"
    return expr


def _to_script(content: str, table: dict):
    """Return the Unicode super/subscript form, or None if not fully mappable."""
    content = content.strip()
    if not content:
        return None
    mapped = [table.get(ch) for ch in content]
    if all(m is not None for m in mapped):
        return "".join(mapped)
    return None


# ---------------------------------------------------------------------------
# Core recursive conversion
# ---------------------------------------------------------------------------

def _convert(s: str) -> str:
    """Convert a LaTeX fragment (delimiters already stripped) to plain text."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]

        # ---- backslash commands ----------------------------------------
        if c == "\\":
            m = _CMD_RE.match(s, i)
            if not m:
                # escaped punctuation like \{ \} \% \& \_ \$ \# \\ or \, \; \:
                nxt = s[i + 1] if i + 1 < n else ""
                if nxt in "{}%&_$#":
                    out.append(nxt)
                    i += 2
                    continue
                if nxt == "\\":  # line break inside math
                    out.append("\n")
                    i += 2
                    continue
                if nxt in ",;:! ":
                    out.append(" " if nxt != "!" else "")
                    i += 2
                    continue
                out.append("")  # stray backslash
                i += 1
                continue

            cmd = m.group(1)
            j = m.end()

            if cmd in ("frac", "dfrac", "tfrac", "cfrac"):
                num, j = _read_group(s, _skip_ws(s, j))
                den, j2 = _read_group(s, _skip_ws(s, j))
                if num is not None and den is not None:
                    out.append(f"{_wrap(_convert(num))}/{_wrap(_convert(den))}")
                    i = j2
                    continue
                out.append("/")
                i = j
                continue

            if cmd == "sqrt":
                # optional [n] index
                root = None
                k = _skip_ws(s, j)
                if k < n and s[k] == "[":
                    end = s.find("]", k)
                    if end != -1:
                        root = s[k + 1:end]
                        k = end + 1
                inner, j2 = _read_group(s, _skip_ws(s, k))
                if inner is not None:
                    body = _convert(inner)
                    body = body if len(body.strip()) <= 1 else f"({body})"
                    prefix = (_to_script(root, _SUP) or f"{root}√") if root else ""
                    if prefix.endswith("√"):
                        out.append(f"{prefix}{body}")
                    else:
                        out.append(f"{prefix}√{body}")
                    i = j2
                    continue
                out.append("√")
                i = k
                continue

            if cmd in _UNWRAP_CMDS:
                inner, j2 = _read_group(s, _skip_ws(s, j))
                if inner is not None:
                    out.append(_convert(inner))
                    i = j2
                    continue
                out.append("")
                i = j
                continue

            if cmd in ("left", "right", "bigl", "bigr", "Bigl", "Bigr",
                       "displaystyle", "textstyle", "limits", "nolimits"):
                # delimiters like \left( \right] — drop the command, keep the
                # bracket that follows (handled on the next loop iteration)
                if cmd in ("left", "right") and j < n and s[j] in "()[]{}|.":
                    ch = s[j]
                    out.append("" if ch == "." else ch)
                    i = j + 1
                    continue
                i = j
                continue

            if cmd in _SPACING:
                out.append(_SPACING[cmd])
                i = j
                continue

            if cmd in _SYMBOLS:
                out.append(_SYMBOLS[cmd])
                i = j
                continue

            # unknown command: drop the backslash, keep the name (best effort)
            out.append(cmd)
            i = j
            continue

        # ---- superscript ----------------------------------------------
        if c == "^":
            grp, j = _read_group(s, i + 1)
            if grp is not None:
                conv = _convert(grp)
                mapped = _to_script(conv, _SUP)
                out.append(mapped if mapped is not None else f"^({conv})")
                i = j
                continue
            # exponent is a command, e.g. ^\circ -> °
            if i + 1 < n and s[i + 1] == "\\":
                m2 = _CMD_RE.match(s, i + 1)
                if m2:
                    out.append(_SYMBOLS.get(m2.group(1), m2.group(1)))
                    i = m2.end()
                    continue
            # single token exponent
            if i + 1 < n:
                tok = s[i + 1]
                out.append(_SUP.get(tok, f"^{tok}"))
                i += 2
                continue
            out.append("^")
            i += 1
            continue

        # ---- subscript ------------------------------------------------
        if c == "_":
            grp, j = _read_group(s, i + 1)
            if grp is not None:
                conv = _convert(grp)
                mapped = _to_script(conv, _SUB)
                out.append(mapped if mapped is not None else f"_({conv})")
                i = j
                continue
            if i + 1 < n and s[i + 1] == "\\":
                m2 = _CMD_RE.match(s, i + 1)
                if m2:
                    out.append(_SYMBOLS.get(m2.group(1), m2.group(1)))
                    i = m2.end()
                    continue
            if i + 1 < n:
                tok = s[i + 1]
                out.append(_SUB.get(tok, f"_{tok}"))
                i += 2
                continue
            out.append("_")
            i += 1
            continue

        # ---- stray braces ---------------------------------------------
        if c in "{}":
            i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t":
        i += 1
    return i


# ---------------------------------------------------------------------------
# Delimiter handling (public entry point)
# ---------------------------------------------------------------------------

# Display / inline math delimiters. Order matters: $$ before $.
_DISPLAY_BRACKET = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_INLINE_PAREN = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
_DOUBLE_DOLLAR = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
# Single $...$ on one line, avoiding escaped \$ and empty $$.
_SINGLE_DOLLAR = re.compile(r"(?<!\\)\$(?!\$)([^\n$]+?)(?<!\\)\$")


def _sub_math(pattern: re.Pattern, text: str) -> str:
    return pattern.sub(lambda mm: _convert(mm.group(1)).strip(), text)


# Inner content must contain a LaTeX command / sup / sub to be treated as math;
# otherwise ``$5 and $10`` (currency) would be wrongly consumed as a math span.
_MATH_MARKER = re.compile(r"[\\^_]")


def _sub_single_dollar(text: str) -> str:
    def repl(mm):
        inner = mm.group(1)
        if not _MATH_MARKER.search(inner):
            return mm.group(0)  # leave currency / plain text untouched
        return _convert(inner).strip()

    return _SINGLE_DOLLAR.sub(repl, text)


def _convert_math(text: str) -> str:
    """Run all delimiter substitutions on a chunk of non-code text."""
    text = _sub_math(_DOUBLE_DOLLAR, text)
    text = _sub_math(_DISPLAY_BRACKET, text)
    text = _sub_math(_INLINE_PAREN, text)
    text = _sub_single_dollar(text)
    return text


# Markdown code spans whose contents must NOT be converted (they may legitimately
# contain LaTeX or ``$`` we should preserve verbatim). Fenced blocks first, then
# double- and single-backtick inline code.
_CODE_SPAN = re.compile(
    r"```[\s\S]*?```"      # fenced ``` ... ```
    r"|~~~[\s\S]*?~~~"      # fenced ~~~ ... ~~~
    r"|``[\s\S]*?``"        # double-backtick inline code
    r"|`[^`\n]*`"           # single-backtick inline code
)


def latex_to_text(text: str) -> str:
    """Convert LaTeX math in ``text`` to readable plain (Unicode) text.

    Handles ``\\[..\\]``, ``\\(..\\)``, ``$$..$$`` and ``$..$`` delimiters and a
    broad set of common commands (fractions, roots, powers, Greek letters,
    operators). Markdown code spans are left untouched so LaTeX/``$`` shown as
    code survives verbatim. Non-math text is returned unchanged. Safe on
    ``None``/empty.
    """
    if not text:
        return text or ""

    parts = []
    last = 0
    for match in _CODE_SPAN.finditer(text):
        parts.append(_convert_math(text[last:match.start()]))
        parts.append(match.group(0))  # code span preserved verbatim
        last = match.end()
    parts.append(_convert_math(text[last:]))
    return "".join(parts)


__all__ = ["latex_to_text"]
