/**
 * Convert LaTeX math notation into readable plain (Unicode) text.
 * Safe on null/undefined/non-string.
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
  // Roots / misc symbols
  sqrt: "√", circ: "°", degree: "°",
  // Accents / modifiers
  hat: "^", bar: "¯", vec: "→", dot: "˙", ddot: "¨",
};

const SUPERSCRIPTS = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
  "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
  "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
  "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ",
  "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ",
  "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ",
  "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
  "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
  "A": "ᴬ", "B": "ᴮ", "D": "ᴰ", "E": "ᴱ", "G": "ᴳ",
  "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ",
  "M": "ᴹ", "N": "ᴺ", "O": "ᴼ", "P": "ᴾ", "R": "ᴿ",
  "T": "ᵀ", "U": "ᵁ", "W": "ᵂ",
};

const SUBSCRIPTS = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
  "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
  "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
  "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
  "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
  "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ",
  "v": "ᵥ", "x": "ₓ",
};

function toUnicodeScript(s, map) {
  let res = "";
  for (const ch of s) {
    if (map[ch] !== undefined) {
      res += map[ch];
    } else {
      return null;
    }
  }
  return res;
}

function convert(expr) {
  let s = expr;

  // \text{...}, \mathrm{...}, etc. -> inner text
  s = s.replace(/\\(?:text|mathrm|mathbf|mathit|mathsf|mathtt)\{([^{}]*)\}/g, "$1");

  // \frac{a}{b} -> a/b
  s = s.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, (m, a, b) => {
    const cleanA = a.trim();
    const cleanB = b.trim();
    return `${cleanA}/${cleanB}`;
  });

  // \sqrt{a} -> √a
  s = s.replace(/\\sqrt\{([^{}]*)\}/g, "√$1");

  // Symbols
  s = s.replace(/\\([a-zA-Z]+)/g, (match, name) => {
    if (SYMBOLS[name] !== undefined) {
      return SYMBOLS[name];
    }
    return match;
  });

  // Superscripts ^{...} or ^x
  s = s.replace(/\^\{([^{}]+)\}/g, (m, inner) => {
    const uni = toUnicodeScript(inner, SUPERSCRIPTS);
    return uni !== null ? uni : `^(${inner})`;
  });
  s = s.replace(/\^([0-9a-zA-Z+\-=()])/g, (m, ch) => {
    return SUPERSCRIPTS[ch] !== undefined ? SUPERSCRIPTS[ch] : `^${ch}`;
  });

  // Subscripts _{...} or _x
  s = s.replace(/_\{([^{}]+)\}/g, (m, inner) => {
    const uni = toUnicodeScript(inner, SUBSCRIPTS);
    return uni !== null ? uni : `_(${inner})`;
  });
  s = s.replace(/_([0-9a-zA-Z+\-=()])/g, (m, ch) => {
    return SUBSCRIPTS[ch] !== undefined ? SUBSCRIPTS[ch] : `_${ch}`;
  });

  // Remove spacing commands
  s = s.replace(/\\([,;! ]|quad|qquad)/g, " ");

  // Clean remaining braces
  s = s.replace(/\{([^{}]*)\}/g, "$1");

  return s;
}

function subMath(pattern, text) {
  return text.replace(pattern, (whole, inner) => {
    return convert(inner).trim();
  });
}

const MATH_MARKER = /[\\^_]/;
const subSingleDollar = (text) =>
  text.replace(/(^|[^\\])\$(?!\$)([^\n$]+?)\$/g, (whole, pre, inner) =>
    MATH_MARKER.test(inner) ? pre + convert(inner).trim() : whole
  );

function convertMath(text) {
  let out = text;
  out = subMath(/\$\$([\s\S]+?)\$\$/g, out);
  out = subMath(/\\\[([\s\S]+?)\\\]/g, out);
  out = subMath(/\\\(([\s\S]+?)\\\)/g, out);
  out = subSingleDollar(out);
  return out;
}

const CODE_SPAN = /```[\s\S]*?```|~~~[\s\S]*?~~~|``[\s\S]*?``|`[^`\n]*`/g;

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
    if (m[0].length === 0) CODE_SPAN.lastIndex += 1;
  }
  out += convertMath(text.slice(last));
  return out;
}

export default latexToText;
