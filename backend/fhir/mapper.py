"""FHIR R4 mapper — stub for Phase 2 (govt reporting)."""

from __future__ import annotations

from typing import Optional


def map_to_patient(vitals_data: dict) -> dict:
    demographics = vitals_data.get("PatientDemographics", {})
    return {
        "resourceType": "Patient",
        "name": [{"text": demographics.get("Name", "Unknown")}],
        "gender": "female",
        "birthDate": _age_to_birth_year(demographics.get("Age")),
    }


def map_to_observation(vitals_data: dict, patient_id: str) -> list[dict]:
    vitals = vitals_data.get("Vitals", {})
    observations = []

    if vitals.get("SystolicBP") is not None and vitals.get("DiastolicBP") is not None:
        observations.append({
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel"}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            "component": [
                {"code": {"coding": [{"code": "8480-6"}]}, "valueQuantity": {"value": vitals["SystolicBP"], "unit": "mmHg"}},
                {"code": {"coding": [{"code": "8462-4"}]}, "valueQuantity": {"value": vitals["DiastolicBP"], "unit": "mmHg"}},
            ],
        })

    if vitals.get("WeightKG") is not None:
        observations.append({
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            "valueQuantity": {"value": vitals["WeightKG"], "unit": "kg"},
        })

    return observations


def _age_to_birth_year(age) -> Optional[str]:
    if age is None:
        return None
    from datetime import datetime
    year = datetime.utcnow().year - int(age)
    return f"{year}-01-01"
