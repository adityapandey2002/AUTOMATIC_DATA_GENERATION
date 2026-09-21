"""Free, local Q&A field filler — instant bilingual extraction from transcript.

Designed around the actual Bihar Q&A pattern: the health worker asks a question
and the patient answers with values. This module scans the ASR transcript for
each case-sheet field using lightweight Hindi/English keyword + regex rules.

Used on EVERY chunk (zero cost, instant). Gemini only runs at finalize to
confirm/fill the ambiguous leftovers, so the free-tier quota lasts all day.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ---------------------------------------------------------------- helpers

HINDI_MONTHS = {
    "जनवरी": 1, "फ़रवरी": 2, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4,
    "मई": 5, "जून": 6, "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "अक्टूबर": 10,
    "नवंबर": 11, "दिसंबर": 12,
}

HINDI_DIGITS = {
    "०": 0, "१": 1, "२": 2, "३": 3, "४": 4,
    "५": 5, "६": 6, "७": 7, "८": 8, "९": 9,
}

HINDI_WORDS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "छह": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12, "तेरह": 13,
    "चौदह": 14, "पंद्रह": 15, "सोलह": 16, "सत्रह": 17, "अठारह": 18,
    "उन्नीस": 19, "बीस": 20, "इक्कीस": 21, "बाईस": 22, "तेईस": 23,
    "चौबीस": 24, "पच्चीस": 25, "छब्बीस": 26, "सत्ताईस": 27,
    "अट्ठाईस": 28, "उनतीस": 29, "तीस": 30, "इकतीस": 31, "बत्तीस": 32,
    "तैंतीस": 33, "चौंतीस": 34, "पैंतीस": 35, "छत्तीस": 36,
    "सैंतीस": 37, "अड़तीस": 38, "उनतालीस": 39, "चालीस": 40,
    "इकतालीस": 41, "बयालीस": 42, "तैंतालीस": 43, "चौवालीस": 44,
    "पैंतालीस": 45, "छियालीस": 46, "सैंतालीस": 47, "अड़तालीस": 48,
    "उनचास": 49, "पचास": 50, "साठ": 60, "सत्तर": 70, "अस्सी": 80, "नब्बे": 90,
}
TEN_PLUS = {w for w, n in HINDI_WORDS.items() if n >= 21}


def _to_int(text: str) -> Optional[float]:
    text = text.strip()
    digits = "".join(HINDI_DIGITS.get(c, c) for c in text)
    try:
        return int(digits.replace(" ", ""))
    except ValueError:
        pass
    tokens = [t for t in re.split(r"[\s,]+", text) if t]
    if len(tokens) == 1 and tokens[0] in HINDI_WORDS:
        return HINDI_WORDS[tokens[0]]
    total = 0
    for t in tokens:
        w = t.replace("़", "").replace("ों", "ो")
        if w in HINDI_WORDS:
            total += HINDI_WORDS[w]
    return total or None


def _clean_capture(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" ,;:।?")


def _last(text: str, pattern: str) -> Optional[str]:
    """Match an answer AFTER the question — the patient's eply usually comes
    after the worker's question, so the LAST match is the answer."""
    matches = list(re.finditer(pattern, text))
    if not matches:
        return None
    value = _clean_capture(matches[-1].group(1))
    if not value:
        return None
    if re.fullmatch(r"(क्या|कितनी|कितना|बताइए|बताईए|है|हो|था|थी)", value):
        return None
    return value


# ---------------------------------------------------------------- rules

def _extract_after_question(text: str, question_words: tuple) -> Optional[str]:
    """Find the answer that immediately follows a known question."""
    for q in question_words:
        idx = text.find(q)
        if idx == -1:
            continue
        tail = text[idx + len(q):]
        m = re.search(r"([^?.।]{2,60}?)(?:\s*[?.।]|$)", tail)
        if m:
            return _clean_capture(m.group(1))
    return None


def local_fill(transcript: str) -> dict:
    """Return lightweight {field_key: value} from the transcript."""
    text = transcript or ""
    result: dict[str, Any] = {}
    t = text  # keep original (Devanagari)

    # --- phone: 10-digit sequence -----------------------------------------
    m = re.search(r"(?<!\d)([6-9]\d{9})(?!\d)", text.replace(" ", "")) or \
        re.search(r"(?<!\d)(\d{3}\s*\d{3}\s*\d{4})(?!\d)", text)
    if m:
        result["contact_phone"] = re.sub(r"\s+", "", m.group(1))

    # --- aadhaar: 12-digit ------------------------------------------------
    m = re.search(r"(?<!\d)(\d{4}\s*\d{4}\s*\d{4})(?!\d)", text)
    if m:
        result["aadhaar_number"] = re.sub(r"\s+", "", m.group(1))

    # --- name -------------------------------------------------------------
    name = None
    for m in re.finditer(
        r"नाम\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*है\b|\s*[.?।]|$)", text
    ):
        value = _clean_capture(m.group(1))
        if re.fullmatch(r"(क्या|कितनी|कितना|बताइए|बताईए|बताए|बताएए|कौन|कहाँ)", value):
            continue
        ctx = text[max(0, m.start() - 12):m.start()]
        if re.search(r"(पति|पती|पिता|का\s*\w*$)", ctx):
            continue  # someone else's name — skip
        name = value
    if name:
        result["name"] = name

    # --- spouse / father --------------------------------------------------
    value = _last(text, r"(?:पति|पती)\s*का\s*नाम\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*है\b|\s*[.?।]|$)")
    if value:
        result["spouse_parent_of"] = value

    # --- age --------------------------------------------------------------
    m = re.search(r"उम्र\s*[:]?\s*([\u0900-\u097F\d\s]+?)\s*साल", text) or \
        re.search(r"उम्र\s*[:]?\s*([\d\u0900-\u097F]+)", text)
    if m and m.group(1):
        val = _to_int(m.group(1))
        if val:
            result["age"] = int(val)

    # --- block / district / village ----------------------------------------
    value = _last(text, r"ब्लॉक\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*[,.?।]|\s+है|\s+जिला|$)")
    if value:
        result["block"] = value
    value = _last(text, r"जिला\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*[,.?।]|\s+है|$)")
    if value:
        result["district"] = value
    value = _last(text, r"(?:गाँव|गांव|गाव|ग्राम)\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*[,.?।]|\s+ब्लॉक|\s+जिला|\s+है|$)")
    village = value
    bits = [b for b in (village, result.get("block"), result.get("district")) if b]
    if bits:
        result["address"] = ", ".join(bits)
    value = _last(text, r"पता\s*[:]?\s*([\u0900-\u097F\w\s-]{2,80}?)(?:\s*है\b|\s*[.?।]|$)")
    if value and "address" not in result:
        result["address"] = value

    # --- ASHA --------------------------------------------------------------
    value = _last(text, r"आशा\s*का\s*नाम\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*है\b|\s*[.?।]|$)")
    if value:
        result["asha_name"] = value

    # --- health centre -----------------------------------------------------
    value = _last(text, r"(?:स्वास्थ्य\s*)?केन्द्र\s*[:]?\s*([\u0900-\u097F\w\s-]{2,50}?)(?:\s*है\b|\s*[.?।]|$)")
    if value:
        result["health_centre"] = value

    # --- LMP ---------------------------------------------------------------
    m = re.search(r"(?:अंतिम|आखिरी|एलएमपी|LMP)\s*मासिक\s*धर्म\s*[:]?\s*(\d{1,2})?\s*([\u0900-\u097F]+)", text)
    if m:
        day = _to_int(m.group(1)) if m.group(1) else None
        month = m.group(2)
        for name, num in HINDI_MONTHS.items():
            if name in month:
                if day:
                    result["lmp"] = f"2026-{num:02d}-{int(day):02d}"
                break
    m = re.search(r"LMP\s*[:]?\s*(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})", text)
    if m and "lmp" not in result:
        result["lmp"] = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    # --- Yes/No fields --------------------------------------------------------
    def yesno_after(question_hint: str):
        idx = text.find(question_hint)
        if idx == -1:
            return None
        region = text[idx: idx + 140]
        if re.search(r"(नहीं\b|नहि\b|no\b)", region, re.IGNORECASE):
            return "No"
        if re.search(r"(हाँ|हा\b|जी\s*हाँ|हो\s*गई|हुआ|हुई|yes\b)", region, re.IGNORECASE):
            return "Yes"
        return None

    for hint, key in (
        ("एएनसी", "pregnancy_complication"),
        ("एनसी", "pregnancy_complication"),
        ("एन.सी", "pregnancy_complication"),
        ("जटिलता", "pregnancy_complication"),
        ("जाँच", "pregnancy_complication"),
        ("जांच", "pregnancy_complication"),
    ):
        val = yesno_after(hint)
        if val:
            result.setdefault(key, val)

    # --- baby / delivery keywords ---------------------------------------------
    if re.search(r"सामान्य\s*प्रसव|सामान्य", text):
        result.setdefault("delivery_mode", "Normal")
    if re.search(r"सीज़ेरियन|सिजेरियन|सिजेरियन|caesarean|cesarean", text, re.IGNORECASE):
        result["delivery_mode"] = "Caesarean"
    if re.search(r"जीवित\s*बच्चा|जीवित", text):
        result.setdefault("delivery_outcome", "Live birth")
    if re.search(r"स्टिल\s*बर्थ|मृत\s*जन्म", text):
        result["delivery_outcome"] = "Stillbirth"
    if re.search(r"लड़का|बेटा|बालक", text):
        result.setdefault("baby_sex", "Boy")
    if re.search(r"लड़की|बेटी|बालिका", text):
        result["baby_sex"] = "Girl"
    m = re.search(r"वजन\s*[:]?\s*([\d.,]+)\s*(?:कि\.?ग्रा|किलो|kg)", text, re.IGNORECASE)
    if m:
        try:
            result["birth_weight_kg"] = float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    if re.search(r"प्री-टर्म|समय\s*से\s*पहले|preterm", text, re.IGNORECASE):
        result.setdefault("preterm", "Yes")
    if re.search(r"जुड़वा|जुड़वाँ|जुड़वां|twin", text, re.IGNORECASE):
        result.setdefault("babies_count", "Twin")

    # immunization
    shots = []
    for token, value in (
        ("बीसीजी", "BCG"), ("ओपीवी", "OPV"), ("हेपेटाइटिस", "Hepatitis B"),
        ("विटामिन K1", "Inj. Vitamin K1"), ("ओपीवी", "OPV"), ("बी सी जी", "BCG"),
    ):
        if token in text:
            shots.append(value)
    if shots:
        result["immunization"] = shots

    # --- marital status -----------------------------------------------------
    if re.search(r"विवाहि|शादीशुदा|married", text, re.IGNORECASE):
        result["marital_status"] = "Married"
    elif re.search(r"(अविवाहित|unmarried)", text, re.IGNORECASE):
        result["marital_status"] = "Unmarried"

    # --- referral -----------------------------------------------------------
    m = re.search(r"रेफर|refer", text, re.IGNORECASE)
    if m:
        idx = m.start()
        snippet = _clean_capture(text[max(0, idx - 80): idx + 80])
        result["referred_from"] = snippet or "Yes"

    return {k: v for k, v in result.items() if v not in (None, "", [])}