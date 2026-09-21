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

# Devanagari-safe boundary: \b fails after matras (combining marks are non-word).
# Instead require the next char to be space, punctuation or end-of-string.
BD = r"(?=\s|[.?,।;]|$)"

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
    "उनचास": 49, "पचास": 50, "पचपन": 55, "साठ": 60, "सत्तर": 70,
    "अस्सी": 80, "नब्बे": 90,
}

QUESTION_TOKENS = re.compile(
    r"^(क्या|कितनी|कितना|कितने|बताइए|बताईए|बताए|बताएए|बताओ|कौन|कहाँ|कहां|है|हो|था|थी|थे)$"
)


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
        w = t.replace("़", "")
        if w in HINDI_WORDS:
            total += HINDI_WORDS[w]
    return total or None


def _clean_capture(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" ,;:।?")


def _last(text: str, pattern: str) -> Optional[str]:
    """The patient's answer usually comes AFTER the question, so the LAST
    match is more likely the answer. Drop pure-question tokens."""
    matches = list(re.finditer(pattern, text))
    if not matches:
        return None
    value = _clean_capture(matches[-1].group(1))
    if not value or QUESTION_TOKENS.fullmatch(value):
        return None
    return value


def local_fill(transcript: str) -> dict:
    """Return lightweight {field_key: value} from the transcript."""
    text = transcript or ""
    text = text.replace("गाँव", "गांव")
    result: dict[str, Any] = {}

    # --- phone: 10-digit sequence ----------------------------------------
    m = re.search(r"(?<!\d)([6-9]\d{9})(?!\d)", text.replace(" ", "")) or \
        re.search(r"(?<!\d)(\d{3}\s*\d{3}\s*\d{4})(?!\d)", text)
    if m:
        result["contact_phone"] = re.sub(r"\s+", "", m.group(1))

    # --- aadhaar: 12-digit ------------------------------------------------
    m = re.search(r"(?<!\d)(\d{4}\s*\d{4}\s*\d{4})(?!\d)", text)
    if m:
        result["aadhaar_number"] = re.sub(r"\s+", "", m.group(1))

    # --- name (skip other people's names + question words) -----------------
    name = None
    for m in re.finditer(
        r"नाम\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*है" + BD + r"|\s*[.?।]|$)", text
    ):
        value = _clean_capture(m.group(1))
        if QUESTION_TOKENS.fullmatch(value):
            continue
        ctx = text[max(0, m.start() - 12):m.start()]
        if re.search(r"(पति|पती|पिता|का\s*\w*$)", ctx):
            continue  # someone else's name
        name = value
    if name:
        result["name"] = name

    # --- spouse / father --------------------------------------------------
    value = _last(
        text,
        r"(?:पति|पती)\s*का\s*नाम\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*है"
        + BD + r"|\s*[.?।]|$)",
    )
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
    value = _last(
        text,
        r"ब्लॉक\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*[,.?।]|\s+है"
        + BD + r"|\s+जिला|$)",
    )
    if value:
        result["block"] = value
    value = _last(
        text,
        r"जिला\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*[,.?।]|\s+है"
        + BD + r"|$)",
    )
    if value:
        result["district"] = value
    value = _last(
        text,
        r"(?:गांव|गाव|ग्राम)\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*[,.?।]|\s+ब्लॉक|\s+जिला|\s+है"
        + BD + r"|$)",
    )
    village = value
    bits = [b for b in (village, result.get("block"), result.get("district")) if b]
    if bits:
        result["address"] = ", ".join(bits)
    value = _last(
        text,
        r"पता\s*[:]?\s*([\u0900-\u097F\w\s-]{2,80}?)(?:\s*है" + BD + r"|\s*[.?।]|$)",
    )
    if value and "address" not in result:
        result["address"] = value

    # --- ASHA --------------------------------------------------------------
    value = _last(
        text,
        r"आशा\s*का\s*नाम\s*[:]?\s*([\u0900-\u097F\w\s-]{2,40}?)(?:\s*है"
        + BD + r"|\s*[.?।]|$)",
    )
    if value:
        result["asha_name"] = value

    # --- health centre -----------------------------------------------------
    value = _last(
        text,
        r"(?:स्वास्थ्य\s*)?केन्द्र\s*[:]?\s*([\u0900-\u097F\w\s-]{2,50}?)(?:\s*है"
        + BD + r"|\s*[.?।]|$)",
    )
    if value:
        result["health_centre"] = value

    # --- LMP ---------------------------------------------------------------
    m = re.search(
        r"(?:अंतिम|आखिरी|एलएमपी|LMP)\s*मासिक\s*धर्म\s*[:]?\s*(\d{1,2})?\s*([\u0900-\u097F]{2,12})",
        text,
    )
    if m:
        day = _to_int(m.group(1)) if m.group(1) else None
        month_str = m.group(2)
        for mname, num in HINDI_MONTHS.items():
            if mname in month_str:
                if day:
                    result["lmp"] = f"2026-{num:02d}-{int(day):02d}"
                break
    m = re.search(r"LMP\s*[:]?\s*(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})", text)
    if m and "lmp" not in result:
        result["lmp"] = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    # --- Yes/No fields -----------------------------------------------------
    def yesno_after(question_hint: str):
        idx = text.find(question_hint)
        if idx == -1:
            return None
        tail = text[idx:]
        events = []  # (position, Y/N); the LAST one decides
        for m in re.finditer(r"नहीं" + BD, tail):
            events.append((m.start(), "N"))
        for m in re.finditer(r"हाँ" + BD + r"|जी\s*हाँ", tail):
            events.append((m.start(), "Y"))
        for m in re.finditer(r"हो\s*गई|हो\s*गया|हुई|हुआ|हुआ", tail):
            ctx = tail[max(0, m.start() - 8):m.start()]
            events.append((m.start(), "N" if "नहीं" in ctx else "Y"))
        if not events:
            return None
        return "Yes" if events[-1][1] == "Y" else "No"

    # ANC — "एएनसी/जांच ... हाँ/हो गई" -> anc_checkup_done (+ visit count)
    for hint, key in (
        ("एएनसी", "anc_checkup_done"),
        ("एनसी", "anc_checkup_done"),
        ("एन. सी", "anc_checkup_done"),
        ("एन.सी", "anc_checkup_done"),
    ):
        val = yesno_after(hint)
        if val:
            result.setdefault(key, val)
    for hint in ("एएनसी", "एनसी", "एन. सी", "एन.सी"):
        idx = text.find(hint)
        if idx != -1:
            region = text[idx: idx + 120]
            m = None
            for fm in re.finditer(r"(\d{1,2}\s*bार|\d{1,2}\s*visits|visits\s*\d{1,2}|([\u0900-\u097F]{2,10})\s*बार)", region, re.IGNORECASE):
                m = fm
            if m:
                grp = m.group(1) or m.group(2)
                val = _to_int(grp)
                if val and 0 <= val <= 20:
                    result["anc_visits"] = int(val)
                    break

    # Complications only from explicit complication wording (not ANC).
    for hint, key in (
        ("जटिलता", "pregnancy_complication"),
        ("परेशानी", "pregnancy_complication"),
    ):
        val = yesno_after(hint)
        if val:
            result.setdefault(key, val)

    # --- baby / delivery keywords -------------------------------------------
    if re.search(r"सामान्य\s*प्रसव|सामान्य", text):
        result.setdefault("delivery_mode", "Normal")
    if re.search(r"सीज़ेरियन|सिजेरियन|सिजेरियन|caesarean|cesarean", text, re.IGNORECASE):
        result["delivery_mode"] = "Caesarean"
    if re.search(r"जीवित\s*बच्चा|जीवित", text):
        result.setdefault("delivery_outcome", "Live birth")
    if re.search(r"स्टिल\s*बर्थ|मृत\s*जन्म|stillbirth", text, re.IGNORECASE):
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

    # --- marital status ----------------------------------------------------
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