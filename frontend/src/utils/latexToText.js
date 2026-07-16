/**
 * Convert LaTeX math notation into readable plain (Unicode) text.
 *
 * The generation model often emits equations wrapped in LaTeX delimiters, e.g.
 *
 *     \[ P(\text{HT}) = \frac{1}{4} \]
 *
 * which renders as raw LaTeX on screen. This turns it into normal text like
 * `P(HT) = 1/4` while preserving meaning.
 *
 * This is a mirror of `backend/app/utils/latex_to_text.py` — keep the two rule
 * tables in sync so on-screen content matches PDF/DOCX downloads exactly.
 */

// LaTeX command name -> Unicode replacement.
const SYMBOLS = {
  // Greek (lowercase)
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε",
  varepsilon: "ε", zeta: "ζ", eta: "η", theta: "θ", vartheta: "θ",
  iota: "ι", kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ",
  pi: "π", varpi: "π", rho: "ρ", varrho: "ρ", sigma: "σ",
  varsigma: "ς", tau: "τ", upsilon: "υ", phi: "φ", varphi: "φ",
  chi: "χ", psi: "ψ", omega: "ω",
  // Greek (uppercase)
  Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ",
  Pi: "Π", Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
  // Binary / relational operators
  times: "×", cdot: "·", div: "÷", pm: "±", mp: "∓", ast: "∗",
  star: "⋆", leq: "≤", le: "≤", geq: "≥", ge: "≥", neq: "≠",
  ne: "≠", approx: "≈", equiv: "≡", sim: "∼", simeq: "≃",
  cong: "≅", propto: "∝", ll: "≪", gg: "≫",
  // Set / logic
  in: "∈", notin: "∉", ni: "∋", subset: "⊂", subseteq: "⊆",
  supset: "⊃", supseteq: "⊇", cup: "∪", cap: "∩", emptyset: "∅",
  varnothing: "∅", setminus: "\\", forall: "∀", exists: "∃",
  nexists: "∄", neg: "¬", lnot: "¬", land: "∧", wedge: "∧",
  lor: "∨", vee: "∨", oplus: "⊕", otimes: "⊗",
  // Big operators
  sum: "Σ", prod: "∏", int: "∫", iint: "∬", iiint: "∭",
  oint: "∮", coprod: "∐", bigcup: "⋃", bigcap: "⋂",
  // Calculus / misc
  partial: "∂", nabla: "∇", infty: "∞", aleph: "ℵ", hbar: "ℏ",
  ell: "ℓ", Re: "ℜ", Im: "ℑ", wp: "℘", angle: "∠",
  perp: "⊥", parallel: "∥", therefore: "∴", because: "∵",
  prime: "′",
  // Arrows
  rightarrow: "→", to: "→", gets: "←", leftarrow: "←",
  leftrightarrow: "↔", Rightarrow: "⇒", implies: "⇒",
  Leftarrow: "⇐", Leftrightarrow: "⇔", iff: "⇔", mapsto: "↦",
  uparrow: "↑", downarrow: "↓",
  // Dots
  ldots: "…", cdots: "…", dots: "…", vdots: "⋮", ddots: "⋱",
  // Misc
  deg: "°", circ: "°", bmod: "mod", pmod: "mod",
};

const SUP = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
  "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "−": "⁻", "=": "⁼",
  "(": "⁽", ")": "⁾", n: "ⁿ", i: "ⁱ", a: "ᵃ", b: "ᵇ", c: "ᶜ",
  d: "ᵈ", e: "ᵉ", x: "ˣ", y: "ʸ",
};
const SUB = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
  "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "−": "₋", "=": "₌",
  "(": "₍", ")": "₎", a: "ₐ", e: "ₑ", i: "ᵢ", j: "ⱼ", n: "ₙ",
  o: "ₒ", x: "ₓ",
};

const UNWRAP_CMDS = new Set([
  "text", "textrm", "textbf", "textit", "textsf", "texttt", "mathrm",
  "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathbb", "mathfrak",
  "operatorname", "boldsymbol", "bm", "mbox", "hbox",
]);

const SPACING = {
  quad: " ", qquad: "  ", thinspace: " ", medspace: " ",
  thickspace: " ", enspace: " ", space: " ", "!": "",
};

const FRAC_CMDS = new Set(["frac", "dfrac", "tfrac", "cfrac"]);
const DROP_CMDS = new Set([
  "left", "right", "bigl", "bigr", "Bigl", "Bigr",
  "displaystyle", "textstyle", "limits", "nolimits",
]);

const CMD_RE = /\\([a-zA-Z]+)/y;

function skipWs(s, i) {
  while (i < s.length && (s[i] === " " || s[i] === "\t")) i += 1;
  return i;
}

// If s[i] === '{', return [innerContent, indexAfterMatchingBrace], else [null, i].
function readGroup(s, i) {
  if (i >= s.length || s[i] !== "{") return [null, i];
  let depth = 0;
  for (let j = i; j < s.length; j += 1) {
    if (s[j] === "{") depth += 1;
    else if (s[j] === "}") {
      depth -= 1;
      if (depth === 0) return [s.slice(i + 1, j), j + 1];
    }
  }
  return [null, i]; // unbalanced
}

function wrap(expr) {
  const e = expr.trim();
  if (e.length <= 1) return e;
  if (e.startsWith("(") && e.endsWith(")")) return e;
  if (/[+\-−×÷/=<>±\s]/.test(e)) return `(${e})`;
  return e;
}

// Return the Unicode super/subscript form, or null if not fully mappable.
function toScript(content, table) {
  const c = content.trim();
  if (!c) return null;
  let out = "";
  for (const ch of c) {
    if (table[ch] === undefined) return null;
    out += table[ch];
  }
  return out;
}

// Convert a LaTeX fragment (delimiters already stripped) to plain text.
function convert(s) {
  let out = "";
  let i = 0;
  const n = s.length;
  while (i < n) {
    const c = s[i];

    if (c === "\\") {
      CMD_RE.lastIndex = i;
      const m = CMD_RE.exec(s);
      if (!m || m.index !== i) {
        const nxt = i + 1 < n ? s[i + 1] : "";
        if ("{}%&_$#".includes(nxt)) { out += nxt; i += 2; continue; }
        if (nxt === "\\") { out += "\n"; i += 2; continue; }
        if (",;:! ".includes(nxt)) { out += nxt === "!" ? "" : " "; i += 2; continue; }
        i += 1; // stray backslash
        continue;
      }

      const cmd = m[1];
      let j = i + m[0].length;

      if (FRAC_CMDS.has(cmd)) {
        const [num, j1] = readGroup(s, skipWs(s, j));
        const [den, j2] = readGroup(s, skipWs(s, j1));
        if (num !== null && den !== null) {
          out += `${wrap(convert(num))}/${wrap(convert(den))}`;
          i = j2;
          continue;
        }
        out += "/";
        i = j;
        continue;
      }

      if (cmd === "sqrt") {
        let root = null;
        let k = skipWs(s, j);
        if (k < n && s[k] === "[") {
          const end = s.indexOf("]", k);
          if (end !== -1) { root = s.slice(k + 1, end); k = end + 1; }
        }
        const [inner, j2] = readGroup(s, skipWs(s, k));
        if (inner !== null) {
          let body = convert(inner);
          body = body.trim().length <= 1 ? body : `(${body})`;
          const prefix = root ? (toScript(root, SUP) || `${root}√`) : "";
          out += prefix.endsWith("√") ? `${prefix}${body}` : `${prefix}√${body}`;
          i = j2;
          continue;
        }
        out += "√";
        i = k;
        continue;
      }

      if (UNWRAP_CMDS.has(cmd)) {
        const [inner, j2] = readGroup(s, skipWs(s, j));
        if (inner !== null) { out += convert(inner); i = j2; continue; }
        i = j;
        continue;
      }

      if (DROP_CMDS.has(cmd)) {
        if ((cmd === "left" || cmd === "right") && j < n && "()[]{}|.".includes(s[j])) {
          out += s[j] === "." ? "" : s[j];
          i = j + 1;
          continue;
        }
        i = j;
        continue;
      }

      if (SPACING[cmd] !== undefined) { out += SPACING[cmd]; i = j; continue; }
      if (SYMBOLS[cmd] !== undefined) { out += SYMBOLS[cmd]; i = j; continue; }

      out += cmd; // unknown command: keep the name
      i = j;
      continue;
    }

    if (c === "^") {
      const [grp, j] = readGroup(s, i + 1);
      if (grp !== null) {
        const conv = convert(grp);
        const mapped = toScript(conv, SUP);
        out += mapped !== null ? mapped : `^(${conv})`;
        i = j;
        continue;
      }
      if (i + 1 < n && s[i + 1] === "\\") {
        CMD_RE.lastIndex = i + 1;
        const m2 = CMD_RE.exec(s);
        if (m2 && m2.index === i + 1) {
          out += SYMBOLS[m2[1]] !== undefined ? SYMBOLS[m2[1]] : m2[1];
          i = i + 1 + m2[0].length;
          continue;
        }
      }
      if (i + 1 < n) { const t = s[i + 1]; out += SUP[t] !== undefined ? SUP[t] : `^${t}`; i += 2; continue; }
      out += "^"; i += 1; continue;
    }

    if (c === "_") {
      const [grp, j] = readGroup(s, i + 1);
      if (grp !== null) {
        const conv = convert(grp);
        const mapped = toScript(conv, SUB);
        out += mapped !== null ? mapped : `_(${conv})`;
        i = j;
        continue;
      }
      if (i + 1 < n && s[i + 1] === "\\") {
        CMD_RE.lastIndex = i + 1;
        const m2 = CMD_RE.exec(s);
        if (m2 && m2.index === i + 1) {
          out += SYMBOLS[m2[1]] !== undefined ? SYMBOLS[m2[1]] : m2[1];
          i = i + 1 + m2[0].length;
          continue;
        }
      }
      if (i + 1 < n) { const t = s[i + 1]; out += SUB[t] !== undefined ? SUB[t] : `_${t}`; i += 2; continue; }
      out += "_"; i += 1; continue;
    }

    if (c === "{" || c === "}") { i += 1; continue; }

    out += c;
    i += 1;
  }
  return out;
}

const subMath = (re, text) =>
  text.replace(re, (_, inner) => convert(inner).trim());

// Inner content must look like math (contain a command / sup / sub); otherwise
// `$5 and $10` (currency) would be wrongly consumed as a math span. The leading
// `(^|[^\\])` group replaces a lookbehind (unsupported on Safari < 16.4) — it
// captures the char before `$` so we can re-emit it and skip escaped `\$`.
const MATH_MARKER = /[\\^_]/;
const subSingleDollar = (text) =>
  text.replace(/(^|[^\\])\$(?!\$)([^\n$]+?)\$/g, (whole, pre, inner) =>
    MATH_MARKER.test(inner) ? pre + convert(inner).trim() : whole
  );

// Run all delimiter substitutions on a chunk of non-code text.
function convertMath(text) {
  let out = text;
  out = subMath(/\$\$([\s\S]+?)\$\$/g, out);
  out = subMath(/\\\[([\s\S]+?)\\\]/g, out);
  out = subMath(/\\\(([\s\S]+?)\\\)/g, out);
  out = subSingleDollar(out);
  return out;
}

// Markdown code spans whose contents must NOT be converted — mirror of the
// Python regex. Fenced blocks first, then double- and single-backtick inline.
const CODE_SPAN = /```[\s\S]*?```|~~~[\s\S]*?~~~|``[\s\S]*?``|`[^`\n]*`/g;

/**
 * Convert LaTeX math in `text` to readable plain (Unicode) text. Handles
 * \[..\], \(..\), $$..$$ and $..$ delimiters. Markdown code spans are left
 * untouched. Non-math text is unchanged. Safe on null/undefined/non-string.
 * @param {string} text
 * @returns {string}
 */
export function latexToText(text) {
  if (typeof text !== "string" || !text) return text || "";
  let out = "";
  let last = 0;
  CODE_SPAN.lastIndex = 0;
  let m;
  while ((m = CODE_SPAN.exec(text)) !== null) {
    out += convertMath(text.slice(last, m.index));
    out += m[0]; // code span preserved verbatim
    last = m.index + m[0].length;
    if (m[0].length === 0) CODE_SPAN.lastIndex += 1; // guard against zero-width
  }
  out += convertMath(text.slice(last));
  return out;
}

export default latexToText;
