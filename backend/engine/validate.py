"""Validation + alert engine — clinical risk flags for the MCH case sheet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationAlert:
    field: str
    message: str
    severity: str  # warning | critical


NUMERIC_RANGES = {
    "age": (10, 65),
    "birth_weight_kg": (0.4, 8.0),
}

# Keywords that raise a critical flag when found in diagnosis / referral text
CRITICAL_KEYWORDS = [
    "eclampsia", "pre-eclampsia", "preeclampsia", "haemorrhage", "hemorrhage",
    "severe anaemia", "severe anemia", "placenta previa", "abruption",
    "gestational diabetes", "oligohydramnios", "uterine rupture",
    "एक्लेम्पसिया", "प्री-एक्लेम्पसिया", "रक्तस्राव", "अपरा",
]


def validate_case_sheet(snapshot: dict) -> list[ValidationAlert]:
    answers = snapshot.get("answers", {})
    alerts: list[ValidationAlert] = []

    def num(key):
        value = answers.get(key)
        return value if isinstance(value, (int, float)) else None

    age = num("age")
    if age is not None:
        lo, hi = NUMERIC_RANGES["age"]
        if not (lo <= age <= hi):
            alerts.append(ValidationAlert(
                field="age",
                message=f"Age {age} years outside expected range ({lo}–{hi})",
                severity="warning",
            ))

    weight = num("birth_weight_kg")
    if weight is not None:
        lo, hi = NUMERIC_RANGES["birth_weight_kg"]
        if not (lo <= weight <= hi):
            alerts.append(ValidationAlert(
                field="birth_weight_kg",
                message=f"Birth weight {weight} kg outside expected range ({lo}–{hi})",
                severity="warning",
            ))
        elif weight < 2.5:
            alerts.append(ValidationAlert(
                field="birth_weight_kg",
                message=f"Low birth weight: {weight} kg (< 2.5 kg)",
                severity="warning",
            ))

    if answers.get("pregnancy_complication") in ("Yes", "yes", "हाँ"):
        alerts.append(ValidationAlert(
            field="pregnancy_complication",
            message="Patient presented with a pregnancy-related complication",
            severity="warning",
        ))

    if answers.get("preterm") in ("Yes", "yes", "हाँ"):
        alerts.append(ValidationAlert(
            field="preterm",
            message="Preterm delivery flagged — monitor newborn closely",
            severity="warning",
        ))

    if answers.get("referred_from"):
        alerts.append(ValidationAlert(
            field="referred_from",
            message="Patient was referred from another centre — follow up on referral record",
            severity="warning",
        ))

    text_fields = [
        ("provisional_diagnosis", answers.get("provisional_diagnosis")),
        ("final_diagnosis", answers.get("final_diagnosis")),
        ("referred_from", answers.get("referred_from")),
    ]
    for key, value in text_fields:
        if not value:
            continue
        text = str(value).lower()
        for kw in CRITICAL_KEYWORDS:
            if kw in text:
                alerts.append(ValidationAlert(
                    field=key,
                    message=f"{'Provisional' if key == 'provisional_diagnosis' else 'Final'} diagnosis suggests: {value}",
                    severity="critical",
                ))
                break

    outcome = str(answers.get("final_outcome") or "").lower()
    if outcome == "death":
        alerts.append(ValidationAlert(
            field="final_outcome",
            message="Final outcome: maternal death",
            severity="critical",
        ))
    elif outcome == "referral":
        alerts.append(ValidationAlert(
            field="final_outcome",
            message="Patient referred onwards — ensure referral slip completed",
            severity="warning",
        ))

    return alerts