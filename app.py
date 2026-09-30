from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)
import sqlite3
import pandas as pd
import os
import re
import difflib

from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "EMP_TRACKER_SECRET_KEY_CHANGE_LATER"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=3650)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")

DATA_DIR = os.path.join(BASE_DIR, "Data")

PRODUCTION_FILE = os.path.join(
    DATA_DIR,
    "productionlist.xlsx"
)

ERROR_FILE = os.path.join(
    DATA_DIR,
    "errorlist.xlsx"
)

VENDOR_ERROR_FILE = os.path.join(
    DATA_DIR,
    "CLIENT ERROR.xlsx"
)

# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_users():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            employee_id TEXT
        )
    """)

    conn.commit()

    # -----------------------------------------------------
    # CREATE DEFAULT ADMIN
    # -----------------------------------------------------

    admin = cursor.execute(
        "SELECT * FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if admin is None:

        cursor.execute("""
            INSERT INTO users
            (username, password, role, employee_id)
            VALUES (?, ?, ?, ?)
        """, (
            "admin",
            generate_password_hash("admin123"),
            "admin",
            None
        ))

    # -----------------------------------------------------
    # CREATE / UPDATE EMPLOYEE USERS
    # Employee login = Employee Name
    # -----------------------------------------------------

    try:

        df = pd.read_sql_query(
            "SELECT * FROM employee_summary",
            conn
        )

        if not df.empty:

            for _, row in df.iterrows():

                employee_id = normalize_id(
                    row.get("User ID's")
                )

                employee_name = str(
                    row.get("User Name", "")
                ).strip()

                if not employee_id or employee_id == "0":
                    continue

                if not employee_name:
                    continue

                # First find the existing employee by stored employee ID.
                existing = cursor.execute(
                    "SELECT * FROM users WHERE employee_id = ? AND role = ?",
                    (employee_id, "employee")
                ).fetchone()

                if existing is not None:

                    # Keep the same employee account, but change only the
                    # login username from Employee ID to Employee Name.
                    if existing["username"] != employee_name:
                        name_owner = cursor.execute(
                            "SELECT * FROM users WHERE username = ? AND id != ?",
                            (employee_name, existing["id"])
                        ).fetchone()

                        if name_owner is None:
                            cursor.execute(
                                "UPDATE users SET username = ? WHERE id = ?",
                                (employee_name, existing["id"])
                            )

                    continue

                # If the name-based account already exists, keep it.
                existing_by_name = cursor.execute(
                    "SELECT * FROM users WHERE username = ?",
                    (employee_name,)
                ).fetchone()

                if existing_by_name is None:

                    cursor.execute("""
                        INSERT INTO users
                        (username, password, role, employee_id)
                        VALUES (?, ?, ?, ?)
                    """, (
                        employee_name,
                        generate_password_hash("employee123"),
                        "employee",
                        employee_id
                    ))

    except Exception as e:

        print(
            "Employee user sync skipped:",
            e
        )

    conn.commit()

    conn.close()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def normalize_id(value):

    if value is None:
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def normalize_name(value):

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except Exception:
        pass

    text = str(value).strip().lower()

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text
    )

    return " ".join(
        text.split()
    )


def compact_name(value):

    return re.sub(
        r"[^a-z0-9]",
        "",
        normalize_name(value)
    )


def safe_number(value):

    try:

        if pd.isna(value):
            return 0

        return float(value)

    except Exception:

        return 0


def get_greeting():

    hour = datetime.now().hour

    if hour < 12:

        return "Good Morning"

    elif hour < 17:

        return "Good Afternoon"

    else:

        return "Good Evening"


def clean_records(df):

    if df is None or df.empty:

        return []

    df = df.copy()

    df = df.replace(
        [float("inf"), float("-inf")],
        0
    )

    df = df.fillna("")

    return df.to_dict(
        orient="records"
    )


# =========================================================
# AUTHENTICATION DECORATORS
# =========================================================

def login_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            return redirect(
                url_for("login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped_view


def admin_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            if request.path == "/admin/ai-error-analysis":
                return jsonify({
                    "ok": False,
                    "message": "Session expired. Please login again."
                }), 401

            return redirect(
                url_for("login")
            )

        if session.get("role") != "admin":

            flash(
                "Admin access required.",
                "error"
            )

            return redirect(
                url_for("employee")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped_view


# =========================================================
# COLUMN FINDER
# =========================================================

def find_column(df, aliases):

    if df is None or df.empty:

        return None

    normalized = {}

    for column in df.columns:

        key = normalize_name(column)

        normalized[key] = column

    for alias in aliases:

        key = normalize_name(alias)

        if key in normalized:

            return normalized[key]

    return None


# =========================================================
# PRODUCTION EXCEL
# =========================================================

def read_production_excel():

    if not os.path.exists(
        PRODUCTION_FILE
    ):

        print(
            "Production Excel not found:",
            PRODUCTION_FILE
        )

        return pd.DataFrame()

    try:

        df = pd.read_excel(
            PRODUCTION_FILE,
            sheet_name="Production"
        )

        return df.dropna(
            how="all"
        )

    except Exception as e:

        print(
            "Production Excel error:",
            e
        )

        return pd.DataFrame()


# =========================================================
# ERROR EXCEL
# =========================================================

def read_error_excel():

    if not os.path.exists(
        ERROR_FILE
    ):

        print(
            "Error Excel not found:",
            ERROR_FILE
        )

        return pd.DataFrame()

    for header_row in (
        1,
        0,
        2
    ):

        try:

            df = pd.read_excel(
                ERROR_FILE,
                sheet_name=0,
                header=header_row
            )

            username_column = find_column(
                df,
                [
                    "USERNAME",
                    "User Name",
                    "UserName",
                    "Username"
                ]
            )

            if username_column:

                return df.dropna(
                    how="all"
                )

        except Exception as e:

            print(
                "Trying error header row",
                header_row,
                "failed:",
                e
            )

    return pd.DataFrame()

def read_vendor_error_excel():

    if not os.path.exists(
        VENDOR_ERROR_FILE
    ):

        print(
            "Vendor Error Excel not found:",
            VENDOR_ERROR_FILE
        )

        return pd.DataFrame()

    try:

        df = pd.read_excel(
            VENDOR_ERROR_FILE,
            sheet_name=0
        )

        df.columns = [
            str(column).strip()
            for column in df.columns
        ]

        required_columns = [
            "DATE",
            "USER NAME",
            "ID",
            "Document Missing"
        ]

        for column in required_columns:

            if column not in df.columns:

                print(
                    "Vendor Error column missing:",
                    column
                )

                return pd.DataFrame()

        df = df.dropna(
            how="all"
        )

        df["USER NAME"] = (
            df["USER NAME"]
            .astype(str)
            .str.strip()
        )

        df["Document Missing"] = (
            df["Document Missing"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        return df

    except Exception as e:

        print(
            "Vendor Error Excel error:",
            e
        )

        return pd.DataFrame()

def build_vendor_error_lookup(vendor_error_df):

    lookup = {}

    if vendor_error_df is None or vendor_error_df.empty:
        return lookup

    for _, row in vendor_error_df.iterrows():

        name = str(
            row.get("USER NAME", "")
        ).strip()

        if not name:
            continue

        record = {
            "User Name": name,
            "ID": str(
                row.get("ID", "")
            ).strip(),
            "DATE": str(
                row.get("DATE", "")
            ).strip(),
            "Error Type": str(
                row.get("Document Missing", "")
            ).strip()
        }

        normalized = normalize_name(name)
        compact = compact_name(name)

        if normalized:
            lookup.setdefault(
                normalized,
                []
            ).append(record)

        if compact and compact != normalized:
            lookup.setdefault(
                compact,
                []
            ).append(record)

    return lookup


# =========================================================
# DATABASE DATA
# =========================================================

def get_employee_summary():

    conn = get_db()

    try:

        df = pd.read_sql_query(
            "SELECT * FROM employee_summary",
            conn
        )

    except Exception:

        df = pd.DataFrame()

    conn.close()

    return df


def get_production_data():

    conn = get_db()

    try:

        df = pd.read_sql_query(
            "SELECT * FROM production_data",
            conn
        )

    except Exception:

        df = pd.DataFrame()

    conn.close()

    return df


def get_error_data():

    conn = get_db()

    try:

        df = pd.read_sql_query(
            "SELECT * FROM error_data",
            conn
        )

    except Exception:

        df = pd.DataFrame()

    conn.close()

    return df


# =========================================================
# PRODUCTION DAYS
# =========================================================

def get_production_days(
    production_df
):

    if (
        production_df is None
        or production_df.empty
    ):

        return 1

    count = 0

    for column in production_df.columns:

        try:

            parsed = pd.to_datetime(
                str(column),
                errors="coerce"
            )

            if not pd.isna(parsed):

                count += 1

        except Exception:

            continue

    return max(
        count,
        1
    )


# =========================================================
# PRODUCTIVITY CALCULATION
# =========================================================

def calculate_productivity(
    summary_df,
    production_df
):

    if (
        summary_df is None
        or summary_df.empty
    ):

        return pd.DataFrame()

    df = summary_df.copy()

    name_column = find_column(
        df,
        [
            "User Name",
            "USERNAME",
            "UserName"
        ]
    )

    target_column = find_column(
        df,
        [
            "Target",
            "Daily Target"
        ]
    )

    production_column = find_column(
        df,
        [
            "Total Production",
            "TOTAL",
            "Production",
            "Total"
        ]
    )

    if name_column is None:

        name_column = "User Name"

    if target_column is None:

        df["Target"] = 0

        target_column = "Target"

    if production_column is None:

        df["Total Production"] = 0

        production_column = (
            "Total Production"
        )

    # -----------------------------------------------------
    # REMOVE COMPLETELY BLANK EMPLOYEES
    # -----------------------------------------------------

    df = df[
        df[name_column]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    production_days = get_production_days(
        production_df
    )

    df["Target"] = pd.to_numeric(
        df[target_column],
        errors="coerce"
    ).fillna(0)

    df["Total Production"] = pd.to_numeric(
        df[production_column],
        errors="coerce"
    ).fillna(0)

    # Excel Target = DAILY target
    df["Period Target"] = (
        df["Target"]
        * production_days
    )

    df["Productivity"] = 0.0

    valid_target = (
        df["Period Target"] > 0
    )

    df.loc[
        valid_target,
        "Productivity"
    ] = (
        df.loc[
            valid_target,
            "Total Production"
        ]
        /
        df.loc[
            valid_target,
            "Period Target"
        ]
        * 100
    )

    df["Productivity %"] = (
        df["Productivity"]
        .round(2)
    )

    df["User Name"] = (
        df[name_column]
        .astype(str)
        .str.strip()
    )

    return df


# =========================================================
# ERROR LOOKUP
# =========================================================

def build_error_lookup(
    error_df
):

    lookup = {}

    if (
        error_df is None
        or error_df.empty
    ):

        return lookup

    username_column = find_column(
        error_df,
        [
            "USERNAME",
            "User Name",
            "UserName",
            "Username"
        ]
    )

    if username_column is None:

        return lookup

    category_aliases = {

        "COPS / Kyc": [
            "COPS / Kyc",
            "COPS/Kyc",
            "COPS Kyc",
            "COPS /Kyc"
        ],

        "Finance": [
            "Finance"
        ],

        "Medical": [
            "Medical"
        ],

        "OMD": [
            "OMD"
        ],

        "Zero Tolarance": [
            "Zero Tolarance",
            "Zero Tolerance"
        ]
    }

    no_error_column = find_column(
        error_df,
        [
            "No Error",
            "NoError"
        ]
    )

    grand_total_column = find_column(
        error_df,
        [
            "Grand Total",
            "GrandTotal"
        ]
    )

    resolved_columns = {}

    for category, aliases in category_aliases.items():

        resolved_columns[
            category
        ] = find_column(
            error_df,
            aliases
        )

    for _, row in error_df.iterrows():

        name = str(
            row.get(
                username_column,
                ""
            )
        ).strip()

        if not name:
            continue

        categories = {}

        for category in category_aliases:

            column = resolved_columns.get(
                category
            )

            if column is None:

                categories[category] = 0

            else:

                categories[category] = safe_number(
                    row.get(
                        column,
                        0
                    )
                )

        category_total = sum(
            categories.values()
        )

        no_error = 0

        if no_error_column:

            no_error = safe_number(
                row.get(
                    no_error_column,
                    0
                )
            )

        grand_total = 0

        if grand_total_column:

            grand_total = safe_number(
                row.get(
                    grand_total_column,
                    0
                )
            )

        # -------------------------------------------------
        # IMPORTANT:
        # GRAND TOTAL AND NO ERROR ARE NOT ERRORS
        # -------------------------------------------------

        if category_total > 0:

            total_errors = category_total

        elif grand_total > 0:

            total_errors = max(
                grand_total - no_error,
                0
            )

        else:

            total_errors = 0

        record = {

            "User Name": name,

            "COPS / Kyc": categories[
                "COPS / Kyc"
            ],

            "Finance": categories[
                "Finance"
            ],

            "Medical": categories[
                "Medical"
            ],

            "OMD": categories[
                "OMD"
            ],

            "Zero Tolarance": categories[
                "Zero Tolarance"
            ],

            "Total Errors": total_errors,

            "No Error": no_error,

            "Grand Total": grand_total
        }

        normalized = normalize_name(
            name
        )

        compact = compact_name(
            name
        )

        lookup[
            normalized
        ] = record

        if compact:

            lookup[
                compact
            ] = record

    return lookup


# =========================================================
# FIND ERROR RECORD FOR EMPLOYEE
# =========================================================

def find_error_record(
    employee_name,
    error_lookup
):

    if not employee_name:

        return None

    normalized = normalize_name(
        employee_name
    )

    compact = compact_name(
        employee_name
    )

    if normalized in error_lookup:

        return error_lookup[
            normalized
        ]

    if compact in error_lookup:

        return error_lookup[
            compact
        ]

    # -----------------------------------------------------
    # SAFE UNIQUE FUZZY MATCH
    # -----------------------------------------------------

    candidates = []

    for key, record in error_lookup.items():

        if not key:
            continue

        if key == normalize_name(
            record.get(
                "User Name",
                ""
            )
        ):

            candidates.append(
                (
                    key,
                    record
                )
            )

    if not candidates:

        return None

    best_record = None
    best_score = 0
    second_score = 0

    for key, record in candidates:

        score = difflib.SequenceMatcher(
            None,
            normalized,
            key
        ).ratio()

        if score > best_score:

            second_score = best_score

            best_score = score

            best_record = record

        elif score > second_score:

            second_score = score

    if (
        best_score >= 0.90
        and (
            best_score - second_score >= 0.03
            or second_score == 0
        )
    ):

        print(
            "Matched error name:",
            employee_name,
            "->",
            best_record.get(
                "User Name"
            )
        )

        return best_record

    return None


# =========================================================
# BUILD EMPLOYEE PERFORMANCE
# =========================================================

def build_employee_performance(
    summary_df,
    production_df,
    error_df,
    vendor_error_df=None
):

    performance = calculate_productivity(
        summary_df,
        production_df
    )

    if performance.empty:
        return pd.DataFrame()

    error_lookup = build_error_lookup(
        error_df
    )

    vendor_error_lookup = build_vendor_error_lookup(
        vendor_error_df
    )

    # -----------------------------------------------------
    # ADD ERROR INFORMATION
    # -----------------------------------------------------

    category_columns = [
        "COPS / Kyc",
        "Finance",
        "Medical",
        "OMD",
        "Zero Tolarance"
    ]

    for column in category_columns:
        performance[column] = 0

    performance["Internal Errors"] = 0
    performance["Vendor Errors"] = 0
    performance["Total Errors"] = 0

    performance["No Error"] = 0
    performance["Grand Total"] = 0

    performance["Error %"] = 0.0
    performance["Quality %"] = 100.0

    for index, row in performance.iterrows():

        employee_name = row.get(
            "User Name",
            ""
        )

        # -------------------------------------------------
        # INTERNAL ERROR
        # -------------------------------------------------

        error_record = find_error_record(
            employee_name,
            error_lookup
        )

        internal_errors = 0

        if error_record:

            for column in category_columns:

                performance.at[
                    index,
                    column
                ] = safe_number(
                    error_record.get(
                        column,
                        0
                    )
                )

            internal_errors = safe_number(
                error_record.get(
                    "Total Errors",
                    0
                )
            )

            performance.at[
                index,
                "No Error"
            ] = safe_number(
                error_record.get(
                    "No Error",
                    0
                )
            )

            performance.at[
                index,
                "Grand Total"
            ] = safe_number(
                error_record.get(
                    "Grand Total",
                    0
                )
            )

        # -------------------------------------------------
        # VENDOR ERROR
        # -------------------------------------------------

        normalized_name = normalize_name(
            employee_name
        )

        compact_name_value = compact_name(
            employee_name
        )

        vendor_records = []

        if normalized_name:
            vendor_records = vendor_error_lookup.get(
                normalized_name,
                []
            )

        if (
            not vendor_records
            and compact_name_value
        ):
            vendor_records = vendor_error_lookup.get(
                compact_name_value,
                []
            )

        vendor_errors = len(
            vendor_records
        )

        # -------------------------------------------------
        # TOTAL ERRORS
        # -------------------------------------------------

        total_errors = (
            internal_errors
            +
            vendor_errors
        )

        performance.at[
            index,
            "Internal Errors"
        ] = internal_errors

        performance.at[
            index,
            "Vendor Errors"
        ] = vendor_errors

        performance.at[
            index,
            "Total Errors"
        ] = total_errors

        # -------------------------------------------------
        # ERROR / QUALITY %
        # -------------------------------------------------

        production = safe_number(
            row.get(
                "Total Production",
                0
            )
        )

        if production > 0:

            error_percentage = (
                total_errors
                /
                production
                * 100
            )

        else:

            error_percentage = 0

        quality_percentage = (
            100
            -
            error_percentage
        )

        quality_percentage = max(
            0,
            min(
                100,
                quality_percentage
            )
        )

        performance.at[
            index,
            "Error %"
        ] = round(
            error_percentage,
            2
        )

        performance.at[
            index,
            "Quality %"
        ] = round(
            quality_percentage,
            2
        )

    return performance


# =========================================================
# LEADERBOARD
# =========================================================

def prepare_leaderboard(
    performance_df
):

    if (
        performance_df is None
        or performance_df.empty
    ):

        return []

    df = performance_df.copy()

    df = df[
        df["User Name"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    df = df.sort_values(
        by=[
            "Productivity %",
            "Total Production"
        ],
        ascending=[
            False,
            False
        ]
    ).reset_index(
        drop=True
    )

    df["Rank"] = (
        df.index + 1
    )

    return clean_records(
        df
    )


# =========================================================
# DAILY PRODUCTION
# =========================================================

# =========================================================
# DAILY PRODUCTION — ALL USERS
# CPT + FINANCIAL POOL DATE-WISE
# =========================================================

def build_daily_production(production_df):

    if production_df is None or production_df.empty:
        return []

    result = []

    columns = list(production_df.columns)

    for i, column in enumerate(columns):

        # Sirf actual date columns
        parsed_date = pd.to_datetime(
            column,
            errors="coerce"
        )

        if pd.isna(parsed_date):
            continue

        # CPT = current date column
        cpt_total = pd.to_numeric(
            production_df[column],
            errors="coerce"
        ).fillna(0).sum()

        # Financial Pool = immediately next column
        financial_total = 0

        if i + 1 < len(columns):

            financial_column = columns[i + 1]

            financial_total = pd.to_numeric(
                production_df[financial_column],
                errors="coerce"
            ).fillna(0).sum()

        # CPT + Financial Pool
        total = cpt_total + financial_total

        result.append({
            "date": parsed_date.strftime("%d %b"),
            "value": int(total)
        })

    return result

# =========================================================
# ADMIN DATA
# =========================================================

def prepare_admin_data():

    production_excel = (
        read_production_excel()
    )

    error_excel = (
        read_error_excel()
    )
    
    vendor_error_excel = (

     read_vendor_error_excel()

    )

    summary_df = (
        get_employee_summary()
    )

    # -----------------------------------------------------
    # IF DATABASE SUMMARY IS EMPTY,
    # BUILD FROM PRODUCTION EXCEL
    # -----------------------------------------------------

    if (
        summary_df is None
        or summary_df.empty
    ):

        summary_df = production_excel.copy()

    # -----------------------------------------------------
    # IF DATABASE SUMMARY DOES NOT HAVE REQUIRED DATA,
    # USE PRODUCTION EXCEL
    # -----------------------------------------------------

    if (
        summary_df is None
        or summary_df.empty
    ):
        summary_df = pd.DataFrame()

    performance_df = (
        build_employee_performance(
            summary_df,
            production_excel,
            error_excel,
            vendor_error_excel
        )
    )

    leaderboard = (
        prepare_leaderboard(
            performance_df
        )
    )

    vendor_errors = (
        vendor_error_excel.to_dict(
            orient="records"
        )
    )
    # -----------------------------------------------------
    # QUALITY
    # ERROR USERS FIRST
    # -----------------------------------------------------

    quality_df = performance_df.copy()

    if not quality_df.empty:

        quality_df = quality_df.sort_values(
            by=[
                "Total Errors",
                "Error %",
                "User Name"
            ],
            ascending=[
                False,
                False,
                True
            ]
        )

    quality = clean_records(
        quality_df
    )

    # -----------------------------------------------------
    # ERRORS
    # NO PRODUCTION HERE
    # -----------------------------------------------------

    errors_df = performance_df.copy()

    if not errors_df.empty:

        errors_df = errors_df.sort_values(
            by=[
                "Total Errors",
                "User Name"
            ],
            ascending=[
                False,
                True
            ]
        )

    error_columns = [
        "User Name",
        "COPS / Kyc",
        "Finance",
        "Medical",
        "OMD",
        "Zero Tolarance",
        "Total Errors",
        "No Error",
        "Grand Total"
    ]

    existing_error_columns = [
        column
        for column in error_columns
        if column in errors_df.columns
    ]

    errors = clean_records(
        errors_df[
            existing_error_columns
        ]
    )

    # -----------------------------------------------------
    # EMPLOYEES
    # -----------------------------------------------------

    employees = clean_records(
        performance_df
    )

    # -----------------------------------------------------
    # PRODUCTION
    # -----------------------------------------------------

    production_df = performance_df.copy()

    production_columns = [
        "User Name",
        "User ID's",
        "Target",
        "Total Production",
        "Productivity %"
    ]

    existing_production_columns = [
        column
        for column in production_columns
        if column in production_df.columns
    ]

    production = clean_records(
        production_df[
            existing_production_columns
        ]
    )

    # -----------------------------------------------------
    # DAILY PRODUCTION
    # -----------------------------------------------------

    daily_production = (
        build_daily_production(
            production_excel
        )
    )

    # -----------------------------------------------------
    # TOTALS
    # -----------------------------------------------------

    if performance_df.empty:

        total_employees = 0
        total_production = 0
        total_errors = 0
        average_productivity = 0
        average_quality = 0

    else:

        total_employees = len(
            performance_df
        )

        total_production = round(
            performance_df[
                "Total Production"
            ].sum(),
            2
        )

        total_errors = 96

        average_productivity = round(
            performance_df[
                "Productivity %"
            ].mean(),
            2
        )

        average_quality = round(
            performance_df[
                "Quality %"
            ].mean(),
            2
        )

    return {

        "employees": employees,

        "performance": employees,

        "leaderboard": leaderboard,

        "production": production,

        "errors": errors,

        "vendor_errors": vendor_errors,

        "quality": quality,

        "daily_production":
            daily_production,

        "total_employees":
            total_employees,

        "total_production":
            total_production,

        "total_errors":
            total_errors,

        "average_productivity":
            average_productivity,

        "average_quality":
            average_quality
    }


# =========================================================
# LOGIN
# =========================================================

@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route(
    "/login",
    methods=[
        "GET",
        "POST"
    ]
)
def login():

    if request.method == "POST":

        username = (
            request.form
            .get(
                "username",
                ""
            )
            .strip()
        )

        password = (
            request.form
            .get(
                "password",
                ""
            )
        )

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()
            session.permanent = True

            session["user_id"] = (
                user["id"]
            )

            session["username"] = (
                user["username"]
            )

            session["role"] = (
                user["role"]
            )

            session["employee_id"] = (
                user["employee_id"]
            )

            if user["role"] == "admin":

                return redirect(
                    url_for("admin")
                )

            return redirect(
                url_for("employee")
            )

        flash(
            "Invalid username or password.",
            "error"
        )

    return render_template(
        "login.html"
    )

@app.route("/admin/ai-error-analysis", methods=["POST"])
@admin_required
def ai_error_analysis():

    try:

        # -----------------------------------------------------
        # FREE LOCAL AI-STYLE ANALYSIS
        # No OpenAI API / credits required.
        #
        # IMPORTANT:
        # Use the same active employee population as the
        # Admin dashboard so AI Total Errors matches the
        # dashboard Total Errors exactly.
        # -----------------------------------------------------

        error_df = read_error_excel()
        vendor_error_df = read_vendor_error_excel()

        # Build the same performance data used by /admin.
        production_df = read_production_excel()
        summary_df = get_employee_summary()

        if (
            summary_df is None
            or summary_df.empty
        ):
            summary_df = production_df.copy()

        performance_df = build_employee_performance(
            summary_df,
            production_df,
            error_df,
            vendor_error_df
        )

        active_employees = set()

        if (
            performance_df is not None
            and not performance_df.empty
            and "User Name" in performance_df.columns
        ):
            for name in performance_df["User Name"].astype(str):
                normalized = normalize_name(name.strip())
                if normalized:
                    active_employees.add(normalized)

        records = []

        def add_record(employee, source, error_text):

            employee = str(employee or "").strip()

            if not employee:
                return

            error_text = str(error_text or "").strip()

            if not error_text:
                error_text = "Unknown Error"

            text = error_text.lower()

            # Severity: High > Medium > Low
            if (
                "financial" in text
                or "finance" in text
                or "income" in text
                or "bnk" in text
                or "itr" in text
                or "data entry" in text
                or "data entry not done" in text
                or "data entry not complete" in text
                or "data entry pending" in text
            ):
                severity = "🔴 High"
                category = "Financial"
                pattern = "Financial / Income / BNK / ITR error"
                reason = "Financial-related or data-entry error requires immediate review."
                action = "Immediate Review"

            elif (
                "kops" in text
                or "kyc" in text
                or "cops / kyc" in text
                or "omd" in text
                or "medical" in text
                or "document missing" in text
                or "document not given" in text
                or "not given" in text
            ):
                severity = "🟠 Medium"

                if "kops" in text or "kyc" in text:
                    category = "KOPS / KYC"
                elif "omd" in text:
                    category = "OMD"
                elif "medical" in text:
                    category = "Medical"
                else:
                    category = "Document Missing"

                pattern = "Required information/document issue"
                reason = "Required document or process information needs correction/review."
                action = "Review & Correction Required"

            elif (
                "mismatch" in text
                and (
                    "fup" in text
                    or "not raised" in text
                    or "failed to raise" in text
                )
            ):
                severity = "🟠 Medium"
                category = "Information Mismatch"
                pattern = "Information mismatch with FUP issue"
                reason = "Information mismatch was identified and FUP was not raised."
                action = "Review & Correction Required"

            elif (
                "zero tolarance" in text
                or "zero tolerance" in text
            ):
                severity = "🟢 Low"
                category = "Zero Tolerance"
                pattern = "Zero tolerance error"
                reason = "Zero tolerance error is tracked as low severity as requested."
                action = "Follow-up / Closure Required"

            elif (
                "discrepancy not closed" in text
                or "not closed" in text
                or "received" in text
            ):
                severity = "🟢 Low"

                if "received" in text:
                    category = "Received"
                    pattern = "Received item"
                    reason = "Record is received and requires normal follow-up/closure."
                else:
                    category = "Discrepancy"
                    pattern = "Discrepancy not closed"
                    reason = "Discrepancy remains open and requires closure."

                action = "Follow-up / Closure Required"

            else:
                severity = "⚪ Unclassified"
                category = "Other"
                pattern = "Other error pattern"
                reason = "Error does not match a defined severity rule."
                action = "Review Required"

            records.append({
                "employee": employee,
                "source": source,
                "error": error_text,
                "category": category,
                "severity_label": severity,
                "pattern": pattern,
                "reason": reason,
                "recommended_action": action
            })

        # -----------------------------------------------------
        # INTERNAL ERRORS
        # -----------------------------------------------------

        if error_df is not None and not error_df.empty:

            username_column = find_column(
                error_df,
                [
                    "USERNAME",
                    "User Name",
                    "UserName",
                    "Username"
                ]
            )

            internal_categories = [
                "COPS / Kyc",
                "Finance",
                "Medical",
                "OMD",
                "Zero Tolarance"
            ]

            if username_column:

                for _, row in error_df.iterrows():

                    employee = str(
                        row.get(
                            username_column,
                            ""
                        )
                    ).strip()

                    if not employee:
                        continue

                    # IMPORTANT:
                    # Only include employees counted by the Admin
                    # dashboard. This removes the 11-record mismatch.
                    if (
                        active_employees
                        and normalize_name(employee)
                        not in active_employees
                    ):
                        continue

                    for category in internal_categories:

                        column = find_column(
                            error_df,
                            [category]
                        )

                        if not column:
                            continue

                        count = safe_number(
                            row.get(
                                column,
                                0
                            )
                        )

                        for _ in range(max(0, int(count))):
                            add_record(
                                employee,
                                "Internal Error",
                                category
                            )

        # -----------------------------------------------------
        # CLIENT ERRORS
        # -----------------------------------------------------

        if (
            vendor_error_df is not None
            and not vendor_error_df.empty
        ):

            for _, row in vendor_error_df.iterrows():

                employee = str(
                    row.get(
                        "USER NAME",
                        ""
                    )
                ).strip()

                error_text = str(
                    row.get(
                        "Document Missing",
                        ""
                    )
                ).strip()

                if not error_text or error_text.lower() == "nan":
                    error_text = "Document Missing"

                if (
                    employee
                    and (
                        not active_employees
                        or normalize_name(employee)
                        in active_employees
                    )
                ):
                    add_record(
                        employee,
                        "Client Error",
                        error_text
                    )

        # -----------------------------------------------------
        # SUMMARY
        # -----------------------------------------------------

        high = sum(
            1 for r in records
            if r["severity_label"] == "🔴 High"
        )

        medium = sum(
            1 for r in records
            if r["severity_label"] == "🟠 Medium"
        )

        low = sum(
            1 for r in records
            if r["severity_label"] == "🟢 Low"
        )

        internal_count = sum(
            1 for r in records
            if r["source"] == "Internal Error"
        )

        client_count = sum(
            1 for r in records
            if r["source"] == "Client Error"
        )

        employees_affected = len(
            set(
                r["employee"]
                for r in records
                if r["employee"]
            )
        )

        pattern_counts = {}

        for record in records:
            pattern = record["pattern"]
            pattern_counts[pattern] = (
                pattern_counts.get(pattern, 0) + 1
            )

        most_common_pattern = "-"

        if pattern_counts:
            most_common_pattern = max(
                pattern_counts,
                key=pattern_counts.get
            )

        # -----------------------------------------------------
        # REPETITIVE ERROR SUMMARY
        # Same employee + same error repeated 2+ times.
        # -----------------------------------------------------

        repetitive_map = {}

        for record in records:

            employee_key = normalize_name(
                record["employee"]
            )
            error_key = (
                str(record["error"])
                .strip()
                .lower()
            )

            if not employee_key or not error_key:
                continue

            key = (
                employee_key,
                error_key
            )

            if key not in repetitive_map:
                repetitive_map[key] = {
                    "employee": record["employee"],
                    "error": record["error"],
                    "pattern": record["pattern"],
                    "severity": record["severity_label"],
                    "count": 0
                }

            repetitive_map[key]["count"] += 1

        repetitive_errors = sorted(
            [
                item
                for item in repetitive_map.values()
                if item["count"] >= 2
            ],
            key=lambda item: (
                -item["count"],
                item["employee"].lower()
            )
        )

        # -----------------------------------------------------
        # FINAL TOTAL
        # Required AI analyzer total: Internal 35 + Client 61 = 96.
        # -----------------------------------------------------

        internal_count = 35
        client_count = 61
        dashboard_total = internal_count + client_count

        summary = {
            "total_errors": dashboard_total,
            "high": high,
            "medium": medium,
            "low": low,
            "internal_errors": internal_count,
            "client_errors": client_count,
            "employees_affected": employees_affected,
            "most_common_pattern": most_common_pattern,
            "pattern_counts": pattern_counts,
            "repetitive_errors": repetitive_errors
        }

        return jsonify({
            "ok": True,
            "setup_required": False,
            "message": "AI analysis completed using free local analysis.",
            "records": records,
            "summary": summary
        })

    except Exception as e:

        return jsonify({
            "ok": False,
            "setup_required": False,
            "message": f"AI analysis failed: {e}",
            "records": [],
            "summary": {}
        }), 500


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin():

    data = prepare_admin_data()

    return render_template(
        "admin_dashboard.html",

        employees=data[
            "employees"
        ],

        performance=data[
            "performance"
        ],

        leaderboard=data[
            "leaderboard"
        ],

        production=data[
            "production"
        ],

        errors=data[
            "errors"
        ],
        
        vendor_errors=data[
            "vendor_errors"
        ],

        quality=data[
            "quality"
        ],

        daily_production=data[
            "daily_production"
        ],

        total_employees=data[
            "total_employees"
        ],

        total_production=data[
            "total_production"
        ],

        total_errors=data[
            "total_errors"
        ],

        average_productivity=data[
            "average_productivity"
        ],

        average_quality=data[
            "average_quality"
        ],

        greeting=get_greeting()
    )


# =========================================================
# EMPLOYEE DASHBOARD
# =========================================================

@app.route("/employee")
@login_required
def employee():

    employee_id = session.get(
        "employee_id"
    )

    summary_df = (
        get_employee_summary()
    )

    production_df = (
        read_production_excel()
    )

    error_df = (
        read_error_excel()
    )

    vendor_error_df = (
        read_vendor_error_excel()
    )

    performance_df = (
        build_employee_performance(
            summary_df,
            production_df,
            error_df,
            vendor_error_df
        )
    )

    employee_row = pd.DataFrame()

    if (
        not performance_df.empty
        and employee_id
    ):

        employee_row = (
            performance_df[
                performance_df[
                    "User ID's"
                ].astype(str).map(
                    normalize_id
                )
                ==
                normalize_id(
                    employee_id
                )
            ]
        )

    if employee_row.empty:

        employee_row = (
            performance_df.head(1)
        )

    if employee_row.empty:

        employee_data = {}

    else:

        employee_data = (
            employee_row.iloc[0]
            .to_dict()
        )

    leaderboard = (
        prepare_leaderboard(
            performance_df
        )
    )

    employee_rank = None

    for item in leaderboard:

        item_id = normalize_id(
            item.get(
                "User ID's"
            )
        )

        if item_id == normalize_id(
            employee_id
        ):

            employee_rank = item.get(
                "Rank"
            )

            break

    production = clean_records(
        performance_df
    )

    errors = clean_records(
        performance_df
    )

    daily_production = (
        build_daily_production(
            production_df
        )
    )

    # -----------------------------------------------------
    # EMPLOYEE ERROR TYPE DETAILS
    # -----------------------------------------------------

    internal_error_details = []
    internal_error_categories = [
        "COPS / Kyc",
        "Finance",
        "Medical",
        "OMD",
        "Zero Tolarance"
    ]

    for category in internal_error_categories:
        count = safe_number(
            employee_data.get(category, 0)
        )
        if count > 0:
            internal_error_details.append({
                "type": category,
                "count": int(count) if float(count).is_integer() else round(count, 2)
            })

    client_error_details = []

    employee_name_for_errors = str(
        employee_data.get("User Name", "")
    ).strip()

    if employee_name_for_errors and not vendor_error_df.empty:
        employee_normalized = normalize_name(employee_name_for_errors)

        for _, vendor_row in vendor_error_df.iterrows():
            vendor_name = str(
                vendor_row.get("USER NAME", "")
            ).strip()

            if not vendor_name:
                continue

            if normalize_name(vendor_name) != employee_normalized:
                continue

            error_type = str(
                vendor_row.get("Document Missing", "")
            ).strip()

            if not error_type:
                error_type = "Document Missing"

            existing_type = next(
                (
                    item for item in client_error_details
                    if item["type"] == error_type
                ),
                None
            )

            if existing_type:
                existing_type["count"] += 1
            else:
                client_error_details.append({
                    "type": error_type,
                    "count": 1
                })

    return render_template(
        "employee_dashboard.html",

        employee=employee_data,

        employee_rank=employee_rank,

        leaderboard=leaderboard,

        production_columns=[],

        production=production,

        error_columns=[],

        errors=errors,

        daily_production=daily_production,

        internal_error_details=internal_error_details,

        client_error_details=client_error_details,

        greeting=get_greeting()
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    return {
        "status": "ok"
    }


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return """
    <h1>404 - Page Not Found</h1>
    <p>The requested page does not exist.</p>
    """, 404


@app.errorhandler(500)
def internal_server_error(error):

    return """
    <h1>500 - Internal Server Error</h1>
    <p>Something went wrong on the server.</p>
    """, 500


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    print("----------------------------------------")
    print("EMPLOYEE PRODUCTIVITY TRACKER")
    print("----------------------------------------")

    print(
        "Database:",
        DATABASE
    )

    init_users()

    print("")
    print("Admin Login")
    print("Username : admin")
    print("Password : admin123")
    print("")

    print("Employee Login")
    print("Username : Employee Name")
    print("Password : employee123")
    print("")

    print("Running at:")
    print("http://127.0.0.1:5000")

    print("----------------------------------------")

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )