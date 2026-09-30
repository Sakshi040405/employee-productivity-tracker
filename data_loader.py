import os
import sqlite3
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "database.db"
)

DATA_DIR = os.path.join(
    BASE_DIR,
    "Data"
)

PRODUCTION_FILE = os.path.join(
    DATA_DIR,
    "productionlist.xlsx"
)

ERROR_FILE = os.path.join(
    DATA_DIR,
    "errorlist.xlsx"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# NUMBER CLEANING
# ============================================================

def safe_number(value, default=0):

    try:

        if pd.isna(value):
            return default

        if isinstance(value, str):

            value = value.strip()

            if value == "":
                return default

            value = value.replace(",", "")

        return float(value)

    except (ValueError, TypeError):

        return default


# ============================================================
# PRODUCTION EXCEL
# ============================================================

def load_production_excel():

    if not os.path.exists(PRODUCTION_FILE):

        return pd.DataFrame()

    try:

        df = pd.read_excel(
            PRODUCTION_FILE,
            sheet_name="Production"
        )

        df = df.dropna(
            how="all"
        )

        return df

    except Exception as e:

        print(
            f"Error loading production Excel: {e}"
        )

        return pd.DataFrame()


# ============================================================
# ERROR EXCEL
# ============================================================

def load_error_excel():

    if not os.path.exists(ERROR_FILE):

        return pd.DataFrame()

    try:

        # First row contains the actual headers
        df = pd.read_excel(
            ERROR_FILE,
            header=1
        )

        df = df.dropna(
            how="all"
        )

        return df

    except Exception as e:

        print(
            f"Error loading error Excel: {e}"
        )

        return pd.DataFrame()


# ============================================================
# COLUMN FINDER
# ============================================================

def find_column(df, possible_names):

    if df.empty:
        return None

    columns = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for name in possible_names:

        key = str(name).strip().lower()

        if key in columns:

            return columns[key]

    return None


# ============================================================
# EMPLOYEE NAME COLUMN
# ============================================================

def get_employee_name_column(df):

    return find_column(
        df,
        [
            "User Name",
            "USERNAME",
            "Username",
            "Employee Name",
            "Name"
        ]
    )


# ============================================================
# USER ID COLUMN
# ============================================================

def get_user_id_column(df):

    return find_column(
        df,
        [
            "User ID's",
            "User ID",
            "USER ID",
            "Employee ID",
            "ID"
        ]
    )


# ============================================================
# TARGET COLUMN
# ============================================================

def get_target_column(df):

    return find_column(
        df,
        [
            "Target",
            "Daily Target",
            "Daily_Target"
        ]
    )


# ============================================================
# TOTAL PRODUCTION COLUMN
# ============================================================

def get_total_production_column(df):

    return find_column(
        df,
        [
            "Total Production",
            "TOTAL",
            "Production"
        ]
    )


# ============================================================
# CLEAN EMPLOYEE DATA
# ============================================================

def clean_employee_data(df):

    if df.empty:

        return df

    name_column = get_employee_name_column(
        df
    )

    if name_column is None:

        return df

    # Remove completely blank employee rows
    df = df[
        df[name_column]
        .notna()
    ].copy()

    df[name_column] = (
        df[name_column]
        .astype(str)
        .str.strip()
    )

    # Remove accidental blank/string rows
    df = df[
        (df[name_column] != "") &
        (df[name_column].str.lower() != "nan")
    ]

    return df.reset_index(
        drop=True
    )


# ============================================================
# CALCULATE TOTAL PRODUCTION
# ============================================================

def calculate_total_production(df):

    if df.empty:

        return df

    total_column = get_total_production_column(
        df
    )

    # If TOTAL already exists, preserve Excel value
    if total_column is not None:

        df["Total Production"] = (
            pd.to_numeric(
                df[total_column],
                errors="coerce"
            )
            .fillna(0)
        )

        return df

    # Otherwise calculate from date columns
    date_columns = []

    for column in df.columns:

        try:

            parsed = pd.to_datetime(
                column,
                errors="coerce"
            )

            if not pd.isna(parsed):

                date_columns.append(
                    column
                )

        except Exception:

            continue

    if not date_columns:

        df["Total Production"] = 0

        return df

    df["Total Production"] = 0

    for column in date_columns:

        values = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0)

        df["Total Production"] += values

    return df


# ============================================================
# BUILD EMPLOYEE SUMMARY
# ============================================================

def build_employee_summary():

    production_df = load_production_excel()

    if production_df.empty:

        return pd.DataFrame()

    production_df = clean_employee_data(
        production_df
    )

    production_df = calculate_total_production(
        production_df
    )

    name_column = get_employee_name_column(
        production_df
    )

    id_column = get_user_id_column(
        production_df
    )

    target_column = get_target_column(
        production_df
    )

    result = pd.DataFrame()

    result["User Name"] = (
        production_df[name_column]
        if name_column
        else ""
    )

    result["User ID's"] = (
        production_df[id_column]
        if id_column
        else ""
    )

    result["Target"] = (
        pd.to_numeric(
            production_df[target_column],
            errors="coerce"
        ).fillna(0)
        if target_column
        else 0
    )

    result["Total Production"] = (
        pd.to_numeric(
            production_df["Total Production"],
            errors="coerce"
        ).fillna(0)
    )

    # Preserve schedule if available
    schedule_column = find_column(
        production_df,
        ["Schedule"]
    )

    result["Schedule"] = (
        production_df[schedule_column]
        if schedule_column
        else "-"
    )

    # Preserve location if available
    location_column = find_column(
        production_df,
        ["Location"]
    )

    result["Location"] = (
        production_df[location_column]
        if location_column
        else "-"
    )

    return result.reset_index(
        drop=True
    )


# ============================================================
# BUILD ERROR SUMMARY
# ============================================================

def build_error_summary():

    error_df = load_error_excel()

    if error_df.empty:

        return pd.DataFrame()

    name_column = get_employee_name_column(
        error_df
    )

    if name_column is None:

        return pd.DataFrame()

    error_df = clean_employee_data(
        error_df
    )

    result = pd.DataFrame()

    result["User Name"] = (
        error_df[name_column]
    )

    # Keep all actual error categories
    error_columns = []

    for column in error_df.columns:

        column_name = str(
            column
        ).strip().lower()

        if column_name in [
            "username",
            "user name"
        ]:

            continue

        if column_name in [
            "no error",
            "grand total"
        ]:

            continue

        error_columns.append(
            column
        )

    # Convert error columns to numbers
    for column in error_columns:

        result[column] = (
            pd.to_numeric(
                error_df[column],
                errors="coerce"
            )
            .fillna(0)
        )

    # Use Grand Total from Excel when available
    grand_total_column = find_column(
        error_df,
        [
            "Grand Total"
        ]
    )

    if grand_total_column:

        result["Total Errors"] = (
            pd.to_numeric(
                error_df[grand_total_column],
                errors="coerce"
            )
            .fillna(0)
        )

    else:

        if error_columns:

            result["Total Errors"] = (
                result[error_columns]
                .sum(axis=1)
            )

        else:

            result["Total Errors"] = 0

    return result.reset_index(
        drop=True
    )


# ============================================================
# MERGE PRODUCTION + ERRORS
# ============================================================

def load_employee_data():

    production = build_employee_summary()

    errors = build_error_summary()

    if production.empty:

        return production

    if errors.empty:

        production["Total Errors"] = 0

        return production

    merged = production.merge(
        errors[
            [
                "User Name",
                "Total Errors"
            ]
        ],
        on="User Name",
        how="left"
    )

    merged["Total Errors"] = (
        pd.to_numeric(
            merged["Total Errors"],
            errors="coerce"
        )
        .fillna(0)
    )

    return merged


# ============================================================
# SAVE DATA TO SQLITE
# ============================================================

def save_employee_data():

    df = load_employee_data()

    if df.empty:

        print(
            "No employee data found."
        )

        return

    conn = get_connection()

    try:

        df.to_sql(
            "employee_summary",
            conn,
            if_exists="replace",
            index=False
        )

        conn.commit()

        print(
            f"Saved {len(df)} employees "
            "to employee_summary table."
        )

    except Exception as e:

        conn.rollback()

        print(
            f"Database save error: {e}"
        )

    finally:

        conn.close()


# ============================================================
# GET DATA FROM DATABASE
# ============================================================

def get_employee_data():

    conn = get_connection()

    try:

        query = """
            SELECT *
            FROM employee_summary
        """

        df = pd.read_sql_query(
            query,
            conn
        )

        return df

    except Exception:

        return pd.DataFrame()

    finally:

        conn.close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "Loading employee data..."
    )

    df = load_employee_data()

    print(
        f"Employees loaded: {len(df)}"
    )

    if not df.empty:

        print(
            df.head()
        )

    save_employee_data()

    print(
        "Data loading completed."
    )