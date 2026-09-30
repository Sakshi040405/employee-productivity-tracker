"""AI Error Analyzer for EMP Tracker.

The business severity rules are fixed by the project owner. The AI is used
for classification, pattern extraction, reasoning, and recommended action;
severity is enforced locally from the approved rules.
"""

import json
import os
import re

def _text(value):
    return str(value or "").strip()


def classify_severity(description, category=""):
    text = f"{_text(category)} {_text(description)}".lower()

    # Highest priority first.
    if "financial" in text or any(word in text for word in [
        "financial mismatch", "amount mismatch", "amount discrepancy"
    ]):
        return "🔴 High"

    medium_patterns = [
        "kops", "kyc", "cops / kyc", "cops/kyc",
        "omd", "medical",
        "document not given", "document missing",
        "not given", "not provided", "missing document"
    ]

    # Information mismatch is Medium ONLY when FUP was not raised.
    if "mismatch" in text and (
        "fup not raised" in text
        or "failed to raise fup" in text
        or "not raised" in text
        or "fup" in text and ("failed" in text or "not" in text)
    ):
        return "🟠 Medium"

    if any(pattern in text for pattern in medium_patterns):
        return "🟠 Medium"

    if "discrepancy not closed" in text or "not closed" in text or re.search(r"\breceived\b", text):
        return "🟢 Low"

    return "⚪ Unclassified"


def _local_enrichment(record):
    description = _text(record.get("description"))
    category = _text(record.get("category"))
    severity = classify_severity(description, category)

    return {
        "employee": _text(record.get("employee")),
        "source": _text(record.get("source")),
        "description": description,
        "error": description,
        "category": category or "Unclassified",
        "severity": severity,
        "pattern": "",
        "reason": "",
        "recommended_action": ""
    }


def _extract_json(text):
    text = _text(text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


def _free_local_analysis(records):
    """Free offline fallback: analyzes errors without any paid API."""
    prepared = [_local_enrichment(r) for r in records]

    for base in prepared:
        text = f"{base['category']} {base['description']}".lower()
        severity = base["severity"]

        if "financial" in text or "amount" in text:
            base["category"] = "Financial"
            base["pattern"] = "Financial error"
            base["reason"] = "Financial-related error requires immediate review."
        elif any(x in text for x in ("kops", "kyc", "cops / kyc", "cops/kyc")):
            base["category"] = "KOPS / KYC"
            base["pattern"] = "KOPS / KYC issue"
            base["reason"] = "KOPS/KYC error detected in the record."
        elif "omd" in text:
            base["category"] = "OMD"
            base["pattern"] = "OMD issue"
            base["reason"] = "OMD error detected in the record."
        elif "medical" in text:
            base["category"] = "Medical"
            base["pattern"] = "Medical issue"
            base["reason"] = "Medical-related error detected."
        elif any(x in text for x in ("document not given", "document missing", "missing document", "not provided")):
            base["category"] = "Document Missing"
            base["pattern"] = "Document not given"
            base["reason"] = "Required document was not provided."
        elif "mismatch" in text:
            base["category"] = "Information Mismatch"
            base["pattern"] = "Information mismatch"
            base["reason"] = "Information mismatch detected; FUP status was checked for severity."
        elif "discrepancy" in text and "not closed" in text:
            base["category"] = "Discrepancy"
            base["pattern"] = "Discrepancy not closed"
            base["reason"] = "Discrepancy remains open and requires closure."
        elif re.search(r"\breceived\b", text):
            base["category"] = "Received"
            base["pattern"] = "Received"
            base["reason"] = "Record indicates received status."
        else:
            base["pattern"] = base["category"] or "Other"
            base["reason"] = "Pattern identified from the available error description."

        if severity == "🔴 High":
            base["recommended_action"] = "Immediate Review"
        elif severity == "🟠 Medium":
            base["recommended_action"] = "Review & Correction Required"
        elif severity == "🟢 Low":
            base["recommended_action"] = "Follow-up / Closure Required"
        else:
            base["recommended_action"] = "Review Required"

    return {
        "ok": True,
        "setup_required": False,
        "message": "AI analysis completed using free local analysis (no API credits used).",
        "records": prepared,
        "summary": _summary(prepared)
    }


def analyze_error_records(records):
    """Free local analysis. No OpenAI API or credits are required."""
    return _free_local_analysis(records)


def analyze_errors(error_records):
    """Compatibility wrapper for the existing Flask route.

    The Flask app supplies records with an ``error`` field, while the
    analyzer works with ``description``/``category`` fields.
    """
    normalized = []
    for item in error_records or []:
        error_text = _text(item.get("error"))
        normalized.append({
            "employee": _text(item.get("employee")),
            "source": _text(item.get("source")),
            "description": error_text,
            "category": error_text
        })

    result = analyze_error_records(normalized)
    return result.get("summary", {}), result.get("records", [])


def _summary(records):
    high = sum(r["severity"] == "🔴 High" for r in records)
    medium = sum(r["severity"] == "🟠 Medium" for r in records)
    low = sum(r["severity"] == "🟢 Low" for r in records)

    pattern_counts = {}
    employee_counts = {}
    for r in records:
        pattern = _text(r.get("pattern")) or _text(r.get("category")) or "Unclassified"
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        employee = _text(r.get("employee"))
        if employee:
            employee_counts[employee] = employee_counts.get(employee, 0) + 1

    most_common_pattern = max(pattern_counts, key=pattern_counts.get) if pattern_counts else "-"
    affected_employees = len(employee_counts)

    internal_errors = sum(_text(r.get("source")).lower() == "internal error" for r in records)
    client_errors = sum(_text(r.get("source")).lower() == "client error" for r in records)

    return {
        "total_errors": len(records),
        "high": high,
        "medium": medium,
        "low": low,
        "internal_errors": internal_errors,
        "client_errors": client_errors,
        "employees_affected": affected_employees,
        "most_common_pattern": most_common_pattern,
        "pattern_counts": pattern_counts
    }
