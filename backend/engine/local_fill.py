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

# Tokens that must NOT appear inside a captured name phrase (question words,
# pronouns, connectors). Kept here separately so the name Q&A rule can reuse it.
BAD_NAME_TOKENS = re.compile(
    r"^(क्या|कौन|कहाँ|कहां|कितनी|कितना|कितने|बताइए|बताईए|बताए|बताओ|बढ़े|बड़े|बोलिए|बोलो|"
    r"है|हैं|हो|हूं|नहीं|"
    r"आप|आपका|आपकी|आपके|तुम|तुम्हारा|तुम्हारी|तुम्हारे|मेरा|मेरी|मेरे|उसका|उसकी|उनका|उनकी|"
    r"और|का|की|के|को|नाम|उम्र|पता|साल|ठीक|चलिए|आईए|अच्छा|हाँ|हां)$"
)

# Keywords that signal a NEW question/field right after the previous answer
# (used to stop an answer-capture region from bleeding into the next Q&A).
#
# The Devanagari spellings matter: Whisper transliterates the domain vocabulary
# we inject as a prompt, so real transcripts say "एलएमपी" / "प्रसव पीड़ा", never
# the Latin "LMP". A boundary list that only knows the Latin form never fires on
# actual ASR output.
NEXT_QUESTION_RE = re.compile(
    r"आपका|आपकी|आपके|तुम्हारा|तुम्हारी|उम्र|पता|कितनी|कितना|कितने|कहाँ|कहां|कौन|कब|"
    r"गाँव|गांव|जिला|ब्लॉक|स्वास्थ्य|एएनसी|एनसी|एमसीटीएस|आरसीएच|एलएमपी|LMP|"
    r"प्रसव|सामान्य|सीज़ेरियन|सीजेरियन|जुड़वा|गर्भपात|गर्भावस्था|प्री[- ]टर्म|"
    r"शिशु|बीसीजी|बीसीजी|टीकाकरण|रेफर|डिस्चार्ज|पीड़ा|मासिक|धर्म|नंबर|पति|माता|पिता"
)

# A name is a person's name. Clinical/domain words are never part of one, and
# letting them in produced garbage like "शिवानी सामान्य" that then got saved
# as the patient's name. This is a hard stop for the name span specifically, so
# a name can never absorb a field answer even if NEXT_QUESTION_RE changes.
#
# Terms are matched with a trailing BD, not bare. A bare "प्री" (intended for
# "pre-term") also matches inside the name "प्रीति" and silently destroyed it,
# which is exactly the class of bug this list exists to prevent.
_NAME_STOP_TERMS = (
    "प्रसव", "सामान्य", "सीज़ेरियन", "सीजेरियन", "जुड़वा", "गर्भपात",
    "गर्भावस्था", "प्री टर्म", "प्री-टर्म", "शिशु", "बीसीजी", "बीसीजी",
    "टीकाकरण", "रेफर", "डिस्चार्ज", "पीड़ा", "एलएमपी", "एमसीटीएस",
    "आरसीएच", "एनसी", "एएनसी", "मासिक", "धर्म", "नंबर", "उम्र", "पता",
    "साल", "गाँव", "गांव", "जिला", "ब्लॉक", "स्वास्थ्य", "चिकित्सा",
    "पति", "पत्नी", "माता", "पिता", "पुत्र", "पुत्री", "बेटा", "बेटी", "रजा",
)
NAME_STOP_RE = re.compile("|".join(re.escape(t) for t in _NAME_STOP_TERMS) + BD)


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


def _answer_number(text: str, keyword: str, window: int = 24) -> Optional[float]:
    """Extract the numeric ANSWER that follows a question keyword, skipping
    intermediate question words. Handles the real Q&A pattern where the reply
    comes AFTER the question, e.g. 'उम्र क्या है 35' -> 35."""
    idx = text.find(keyword)
    if idx == -1:
        return None
    region = text[idx + len(keyword): idx + len(keyword) + window]
    tokens = [
        w
        for w in re.split(r"[\s,.?।!]+", region)
        if w and not QUESTION_TOKENS.fullmatch(w)
    ]
    if not tokens:
        return None
    # Try longest prefix first: 'पैंतीस साल' fails as a whole, falls back to
    # 'पैंतीस' = 35. '35 साल' -> '35' + then 35. 'क्या है 35' -> 35.
    for n in range(len(tokens), 0, -1):
        val = _to_int(" ".join(tokens[:n]))
        if val:
            return float(val) if isinstance(val, float) else val
    return None


_NAME_WINDOW_CHARS = 40


def _answer_name(text: str, keyword: str = "नाम") -> Optional[str]:
    """Grab the patient's NAME answer that appears AFTER a name question.

    The strict regex can't cross a comma, so real Q&A speech like:
      'आपका नाम बताइए, प्रीति कुमारी'  ->  'प्रीति कुमारी'
    fails with the simple rule. This looks at the region following the
    keyword, skips question words/punctuation, and takes the first plausible
    1-2 word Devanagari phrase that isn't itself a question or a new field.

    The span is bounded three ways, because an unbounded one produced names
    like 'शिवानी सामान्य' -- the delivery-mode answer bleeding into the patient's
    name, which then got persisted as their name:
      * a character window (_NAME_WINDOW_CHARS),
      * NEXT_QUESTION_RE, which signals the next question/field,
      * NAME_STOP_RE, a hard stop on clinical vocabulary.
    """
    idx = text.find(keyword)
    if idx == -1:
        return None
    # Bound the search window. A name follows its question immediately, so a
    # short span is both sufficient and a second guard against a name running
    # on into a later answer.
    region = text[idx + len(keyword): idx + len(keyword) + _NAME_WINDOW_CHARS]
    nq = NEXT_QUESTION_RE.search(region)
    if nq:
        region = region[: nq.start()]
    # Hard stop on domain vocabulary, independent of NEXT_QUESTION_RE.
    stop = NAME_STOP_RE.search(region)
    if stop:
        region = region[: stop.start()]
    tokens = [w for w in re.split(r"[\s,.?।!-]+", region) if w]
    if not tokens:
        return None
    # Drop question/mangled words, accept only clean Devanagari word tokens.
    clean = [
        w for w in tokens
        if not BAD_NAME_TOKENS.fullmatch(w)
        and re.fullmatch(r"[\u0900-\u097F]+", w)
        and len(w) >= 2
    ]
    if len(clean) >= 2:
        return " ".join(clean[:2])   # first name+last name
    if len(clean) == 1:
        return clean[0]
    return None


DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def hindi_normalize(text: str) -> str:
    """Normalize ASR text into the canonical forms the regex rules expect.

    - Devanagari digits -> Latin digits (५ -> 5)
    - Common ASR-collisions of Hindi speech -> normalized spelling
    - Collapse whitespace / stray punctuation
    """
    text = text.strip()
    text = "".join(str(HINDI_DIGITS.get(c, c)) for c in text)
    text = text.replace("गाँव", "गांव")
    text = re.sub(r"[,;]+", ",", text)
    text = re.sub(r"\s+", " ", text)
    return text


def devanagari_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are Devanagari (0..1).

    Whisper/Sarvam sometimes emit Latin-script 'Hinglish' renders of Hindi
    speech (e.g. 'Nam seeta devi hai'). Our regex rules only match Devanagari,
    so such chunks are unusable for field extraction."""
    letters = [c for c in text if (c.isalpha() or c == "़")]
    if not letters:
        return 1.0
    dev = len([c for c in letters if DEVANAGARI_RE.match(c)])
    return dev / len(letters)


# If the transcript is mostly Latin script (Hinglish), regex fill can't match.
# Don't fill anything from it rather than store partially-wrong values.
MIN_DEVANAGARI_RATIO = 0.35


def local_fill(transcript: str) -> dict:
    """Return lightweight {field_key: value} from the transcript."""
    text = hindi_normalize(transcript or "")
    if not text:
        return {}
    # Script-fidelity gate: mostly-Latin transcripts poison every regex below.
    if devanagari_ratio(text) < MIN_DEVANAGARI_RATIO:
        return {}
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
        # The capture class allows spaces, so it runs to the end of the sentence
        # and swept field answers into the name: "नाम शिवानी सामान्य एलएमपी"
        # yielded "शिवानी सामान्य एलएमपी", which was then persisted as the
        # patient's name. A name never contains clinical vocabulary, so cut the
        # span at the first domain term.
        stop = NAME_STOP_RE.search(value)
        if stop:
            value = _clean_capture(value[: stop.start()])
        if not value or QUESTION_TOKENS.fullmatch(value):
            continue
        ctx = text[max(0, m.start() - 12):m.start()]
        if re.search(r"(पति|पती|पिता|का\s*\w*$)", ctx):
            continue  # someone else's name
        name = value
    if not name:
        # Real Q&A speech: 'आपका नाम बताइए, प्रीति कुमारी' — strict regex can't
        # cross a comma, so fall back to capturing the answer after the question.
        name = _answer_name(text, "नाम")
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
        result["husband_name"] = value  # cover page + partograph + hospital copy

    # --- age --------------------------------------------------------------
    # Handles both styles:
    #  - 'उम्र 35' / 'उम्र पैंतीस साल' (value right after keyword)
    #  - 'उम्र क्या है 35' / 'आपकी उम्र क्या है? 35' (answer AFTER the question)
    age = _answer_number(text, "उम्र", window=24)
    if not age:
        m = re.search(r"उम्र\s*[:]?\s*([\u0900-\u097F\d\s]+?)\s*साल", text)
        if m and m.group(1):
            val = _to_int(m.group(1))
            if val:
                age = val
    if age:
        result["age"] = int(age)

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
            # Positive assertion without हाँ/नहीं: "जटिलता है", "प्रसव पीड़ा शुरू है".
            # Skip the question itself ("क्या जटिलता है?") — only trust the answer.
            region = tail
            q = region.find("?")
            if q != -1:
                region = region[q + 1:]
            if "नहीं" in region[:40]:
                return "No"
            m = re.search(r"(?:है|शुरू)", region[:60])
            if m:
                lookback = region[max(0, m.start() - 24): m.start()]
                if re.search(r"क्या|जरूरत|चाहिए", lookback):
                    return None  # still the question, no answer yet
                return "Yes"
            return None
        return "Yes" if events[-1][1] == "Y" else "No"

    # ANC visit count — "एएनसी ... 4 बार" -> anc_visits (प्रसव पूर्व जाँच की संख्या)
    for hint in ("एएनसी", "एनसी", "एन. सी", "एन.सी", "प्रसव पूर्व जाँच"):
        idx = text.find(hint)
        if idx != -1:
            region = text[idx: idx + 120]
            m = None
            for fm in re.finditer(
                r"(\d{1,2})\s*(?:बार|bार|times|visits?)|([\u0900-\u097F]{2,10})\s*बार",
                region,
                re.IGNORECASE,
            ):
                m = fm
            if m:
                grp = m.group(1) or m.group(2)
                val = _to_int(grp)
                if val and 0 <= val <= 20:
                    result["anc_visits"] = int(val)
                    break

    # Admission category (भर्ती की श्रेणी) — priority: complication > labour > referral.
    # Only explicit complication wording counts (not ANC/जांच mentions).
    complication = None
    for hint in ("जटिलता", "परेशानी"):
        val = yesno_after(hint)
        if val:
            complication = val
    if complication == "Yes":
        result["admission_category"] = "With pregnancy-related complication"
    else:
        labour = yesno_after("प्रसव पीड़ा")
        if labour == "Yes":
            result["admission_category"] = "With labour pain"
        else:
            referred = yesno_after("रेफर") or yesno_after("refer")
            if referred == "Yes":
                result["admission_category"] = "Referred from other centre"

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
    if re.search(r"जुड़वा|जुड़वाँ|जुड़वां|twin", text, re.IGNORECASE):
        result.setdefault("babies_count", "Twin")

    # immunization (BCG / OPV / Hep B) + separate Vitamin K1 checkbox
    shots = []
    for token, value in (
        ("बीसीजी", "BCG"), ("ओपीवी", "OPV"), ("हेपेटाइटिस", "Hepatitis B"),
        ("बी सी जी", "BCG"),
    ):
        if token in text:
            shots.append(value)
    if shots:
        result["immunization"] = shots
    if re.search(r"विटामिन\s*K\s*1|विटामिन\s*के\s*वन|vitamin\s*k\s*1", text, re.IGNORECASE):
        result["vitamin_k1"] = "Yes"

    # --- marital status ----------------------------------------------------
    if re.search(r"विवाहि|शादीशुदा|married", text, re.IGNORECASE):
        result["marital_status"] = "Married"
    elif re.search(r"(अविवाहित|unmarried)", text, re.IGNORECASE):
        result["marital_status"] = "Unmarried"

    # --- discharge / final outcome -------------------------------------------
    if re.search(r"मातृ\s*मृत्यु|मृत्यु हो", text):
        result["final_outcome"] = "Death"
    elif re.search(r"लामा|LAMA", text, re.IGNORECASE):
        result["final_outcome"] = "LAMA"
    elif "डिस्चार्ज" in text and re.search(r"रेफर|refer", text, re.IGNORECASE):
        result["final_outcome"] = "Referral"
    elif re.search(r"डिस्चार्ज\s*हो", text):
        result["final_outcome"] = "Discharge"

    return {k: v for k, v in result.items() if v not in (None, "", [])}