import os
import json
from collections import Counter

from openai import OpenAI


# ============================================================
# AI ERROR ANALYZER
# ============================================================

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# ============================================================
# FIXED SEVERITY RULES
# ============================================================

def classify_severity(error_text):

    text = str(error_text or "").strip().lower()

    # HIGH
    if "financial" in text:
        return "High", "🔴 High"

    # MEDIUM
    medium_rules = [
        "kops",
        "kyc",
        "omd",
        "medical",
        "document not given",
        "document not given",
        "mismatch",
        "fup not raised"
    ]

    if any(rule in text for rule in medium_rules):
        return "Medium", "🟠 Medium"

    # LOW
    low_rules = [
        "discrepancy not closed",
        "received"
    ]

    if any(rule in text for rule in low_rules):
        return "Low", "🟢 Low"

    return "Unknown", "⚪ Unknown"


# ============================================================
# CATEGORY
# ============================================================

def detect_category(error_text):

    text = str(error_text or "").lower()

    if "financial" in text:
        return "Financial"

    if "kops" in text or "kyc" in text:
        return "KOPS / KYC"

    if "omd" in text:
        return "OMD"

    if "medical" in text:
        return "Medical"

    if "document" in text and "not given" in text:
        return "Document Missing"

    if "mismatch" in text:
        return "Information Mismatch"

    if "fup" in text:
        return "FUP Issue"

    if "discrepancy" in text:
        return "Discrepancy"

    if "received" in text:
        return "Received"

    return "Other"


# ============================================================
# ACTION
# ============================================================

def recommended_action(severity):

    if severity == "High":
        return "Immediate Review"

    if severity == "Medium":
        return "Review & Correction Required"

    if severity == "Low":
        return "Follow-up / Closure Required"

    return "Manual Review Required"


# ============================================================
# AI ANALYSIS
# ============================================================

def analyze_with_ai(records):

    if not records:
        return []

    prompt = """
You are an Error Analysis AI for an Employee Productivity Tracker.

Analyze BOTH Internal Errors and Client Errors.

IMPORTANT:
Do not change the severity supplied by the system.

Severity rules:

HIGH:
Financial

MEDIUM:
KOPS / KYC
OMD
Medical
Document Not Given
Document given but information mismatch and user failed to raise FUP

LOW:
Document given but discrepancy not closed
Received

Priority:
HIGH > MEDIUM > LOW

For every error return:

employee
source
error
category
severity
pattern
reason
recommended_action

Do not invent facts.

Return valid JSON only.

ERROR RECORDS:
""" + json.dumps(
        records,
        ensure_ascii=False,
        indent=2
    )

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    result = response.output_text.strip()

    try:
        return json.loads(result)

    except json.JSONDecodeError:
        return records


# ============================================================
# FINAL ANALYZER
# ============================================================

def analyze_errors(error_records):

    prepared = []

    for item in error_records:

        error_text = item.get(
            "error",
            ""
        )

        severity, severity_label = classify_severity(
            error_text
        )

        category = detect_category(
            error_text
        )

        prepared.append({
            "employee": item.get(
                "employee",
                ""
            ),

            "source": item.get(
                "source",
                ""
            ),

            "error": error_text,

            "category": category,

            "severity": severity,

            "severity_label": severity_label,

            "recommended_action":
                recommended_action(severity)
        })

    ai_results = analyze_with_ai(
        prepared
    )

    # Re-apply fixed severity rules.
    # AI cannot override your rules.

    for record in ai_results:

        severity, label = classify_severity(
            record.get(
                "error",
                ""
            )
        )

        record["severity"] = severity
        record["severity_label"] = label

        record["recommended_action"] = (
            recommended_action(
                severity
            )
        )

    return build_summary(ai_results), ai_results


# ============================================================
# SUMMARY
# ============================================================

def build_summary(records):

    high = 0
    medium = 0
    low = 0

    internal = 0
    client = 0

    employees = set()
    patterns = Counter()

    for record in records:

        severity = record.get(
            "severity"
        )

        source = str(
            record.get(
                "source",
                ""
            )
        ).lower()

        employee = record.get(
            "employee",
            ""
        )

        if employee:
            employees.add(employee)

        if "internal" in source:
            internal += 1

        if "client" in source:
            client += 1

        if severity == "High":
            high += 1

        elif severity == "Medium":
            medium += 1

        elif severity == "Low":
            low += 1

        pattern = record.get(
            "pattern",
            record.get(
                "category",
                "Unknown"
            )
        )

        if pattern:
            patterns[pattern] += 1

    return {
        "total_errors": len(records),
        "high": high,
        "medium": medium,
        "low": low,
        "internal_errors": internal,
        "client_errors": client,
        "employees_affected": len(employees),
        "most_common_pattern":
            patterns.most_common(1)[0][0]
            if patterns else None,
        "pattern_counts":
            dict(patterns)
    }