import os
import sqlite3
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

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
# SAFE NUMBER
# ============================================================

def safe_number(value):

    try:

        if pd.isna(value):
            return 0

        if isinstance(value, str):

            value = (
                value
                .strip()
                .replace(",", "")
            )

            if value == "":
                return 0

        return float(value)

    except (
        ValueError,
        TypeError
    ):

        return 0


# ============================================================
# LOAD PRODUCTION
# ============================================================

def load_production():

    if not os.path.exists(
        PRODUCTION_FILE
    ):

        print(
            "Production Excel not found."
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
            f"Production loading error: {e}"
        )

        return pd.DataFrame()


# ============================================================
# LOAD ERRORS
# ============================================================

def load_errors():

    if not os.path.exists(
        ERROR_FILE
    ):

        print(
            "Error Excel not found."
        )

        return pd.DataFrame()

    try:

        # Actual headers are on second row
        df = pd.read_excel(
            ERROR_FILE,
            header=1
        )

        return df.dropna(
            how="all"
        )

    except Exception as e:

        print(
            f"Error loading error Excel: {e}"
        )

        return pd.DataFrame()


# ============================================================
# FIND COLUMN
# ============================================================

def find_column(
    df,
    possible_names
):

    if df.empty:
        return None

    normalized = {}

    for column in df.columns:

        normalized[
            str(column)
            .strip()
            .lower()
        ] = column

    for name in possible_names:

        key = (
            str(name)
            .strip()
            .lower()
        )

        if key in normalized:

            return normalized[key]

    return None


# ============================================================
# CLEAN PRODUCTION
# ============================================================

def clean_production(
    df
):

    if df.empty:

        return df

    name_column = find_column(
        df,
        [
            "User Name",
            "USERNAME",
            "Username",
            "Employee Name"
        ]
    )

    if name_column is None:

        return pd.DataFrame()

    df = df[
        df[name_column].notna()
    ].copy()

    df[name_column] = (
        df[name_column]
        .astype(str)
        .str.strip()
    )

    df = df[
        (df[name_column] != "") &
        (df[name_column].str.lower() != "nan")
    ]

    return df.reset_index(
        drop=True
    )


# ============================================================
# GET PRODUCTION DAYS
# ============================================================

def get_production_days(
    df
):

    if df.empty:

        return 1

    days = 0

    for column in df.columns:

        try:

            parsed = pd.to_datetime(
                column,
                errors="coerce"
            )

            if not pd.isna(parsed):

                days += 1

        except Exception:

            pass

    return max(
        days,
        1
    )


# ============================================================
# CALCULATE TOTAL PRODUCTION
#
# Excel structure:
#
# Date       = CPT
# Unnamed    = Financial Pool
#
# Total Production =
# CPT + Financial Pool
# ============================================================

def calculate_total_production(
    df
):

    if df.empty:

        return df

    total_column = find_column(
        df,
        [
            "TOTAL",
            "Total Production"
        ]
    )

    # --------------------------------------------------------
    # If Excel already contains TOTAL, preserve it.
    # --------------------------------------------------------

    if total_column is not None:

        df["Total Production"] = (
            pd.to_numeric(
                df[total_column],
                errors="coerce"
            )
            .fillna(0)
        )

        return df

    # --------------------------------------------------------
    # Otherwise calculate from date columns
    # --------------------------------------------------------

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

    df["Total Production"] = 0

    for column in date_columns:

        df["Total Production"] += (
            pd.to_numeric(
                df[column],
                errors="coerce"
            )
            .fillna(0)
        )

    return df


# ============================================================
# PROCESS PRODUCTION
# ============================================================

def process_production():

    df = load_production()

    if df.empty:

        return pd.DataFrame()

    df = clean_production(
        df
    )

    df = calculate_total_production(
        df
    )

    return df


# ============================================================
# PROCESS ERRORS
# ============================================================

def process_errors():

    df = load_errors()

    if df.empty:

        return pd.DataFrame()

    name_column = find_column(
        df,
        [
            "USERNAME",
            "User Name",
            "Username"
        ]
    )

    if name_column is None:

        return pd.DataFrame()

    df = df[
        df[name_column].notna()
    ].copy()

    df[name_column] = (
        df[name_column]
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # Grand Total from Excel
    # --------------------------------------------------------

    grand_total_column = find_column(
        df,
        [
            "Grand Total"
        ]
    )

    if grand_total_column is not None:

        df["Total Errors"] = (
            pd.to_numeric(
                df[grand_total_column],
                errors="coerce"
            )
            .fillna(0)
        )

    else:

        # ----------------------------------------------------
        # Fallback: sum actual error categories
        # ----------------------------------------------------

        ignored_columns = [
            "username",
            "user name",
            "no error",
            "grand total"
        ]

        error_columns = []

        for column in df.columns:

            normalized = (
                str(column)
                .strip()
                .lower()
            )

            if normalized not in ignored_columns:

                error_columns.append(
                    column
                )

        if error_columns:

            df["Total Errors"] = 0

            for column in error_columns:

                df["Total Errors"] += (
                    pd.to_numeric(
                        df[column],
                        errors="coerce"
                    )
                    .fillna(0)
                )

        else:

            df["Total Errors"] = 0

    return df[
        [
            name_column,
            "Total Errors"
        ]
    ].rename(
        columns={
            name_column: "User Name"
        }
    )


# ============================================================
# BUILD EMPLOYEE PERFORMANCE
# ============================================================

def build_employee_performance():

    production = process_production()

    errors = process_errors()

    if production.empty:

        return pd.DataFrame()

    # --------------------------------------------------------
    # Columns
    # --------------------------------------------------------

    name_column = find_column(
        production,
        [
            "User Name",
            "USERNAME",
            "Username"
        ]
    )

    id_column = find_column(
        production,
        [
            "User ID's",
            "User ID",
            "Employee ID"
        ]
    )

    target_column = find_column(
        production,
        [
            "Target",
            "Daily Target"
        ]
    )

    schedule_column = find_column(
        production,
        [
            "Schedule"
        ]
    )

    location_column = find_column(
        production,
        [
            "Location"
        ]
    )

    # --------------------------------------------------------
    # Create clean result
    # --------------------------------------------------------

    result = pd.DataFrame()

    result["User Name"] = (
        production[name_column]
    )

    if id_column:

        result["User ID's"] = (
            production[id_column]
        )

    else:

        result["User ID's"] = ""

    if schedule_column:

        result["Schedule"] = (
            production[schedule_column]
        )

    else:

        result["Schedule"] = "-"

    if location_column:

        result["Location"] = (
            production[location_column]
        )

    else:

        result["Location"] = "-"

    if target_column:

        result["Target"] = (
            pd.to_numeric(
                production[target_column],
                errors="coerce"
            )
            .fillna(0)
        )

    else:

        result["Target"] = 0

    result["Total Production"] = (
        pd.to_numeric(
            production["Total Production"],
            errors="coerce"
        )
        .fillna(0)
    )

    # --------------------------------------------------------
    # Merge errors
    # --------------------------------------------------------

    if not errors.empty:

        result = result.merge(
            errors,
            on="User Name",
            how="left"
        )

    else:

        result["Total Errors"] = 0

    result["Total Errors"] = (
        pd.to_numeric(
            result["Total Errors"],
            errors="coerce"
        )
        .fillna(0)
    )

    # ========================================================
    # PRODUCTIVITY
    #
    # Target in Excel = DAILY TARGET
    #
    # Period Target =
    # Daily Target × Number of production days
    #
    # Productivity =
    # Total Production / Period Target × 100
    # ========================================================

    production_days = get_production_days(
        production
    )

    result["Production Days"] = (
        production_days
    )

    result["Period Target"] = (
        result["Target"] *
        production_days
    )

    result["Productivity"] = 0.0

    valid_target = (
        result["Period Target"] > 0
    )

    result.loc[
        valid_target,
        "Productivity"
    ] = (
        result.loc[
            valid_target,
            "Total Production"
        ]
        /
        result.loc[
            valid_target,
            "Period Target"
        ]
        * 100
    )

    # ========================================================
    # QUALITY
    #
    # Error % =
    # Total Errors / Total Production × 100
    #
    # Quality % =
    # 100 - Error %
    # ========================================================

    result["Error %"] = 0.0

    valid_production = (
        result["Total Production"] > 0
    )

    result.loc[
        valid_production,
        "Error %"
    ] = (
        result.loc[
            valid_production,
            "Total Errors"
        ]
        /
        result.loc[
            valid_production,
            "Total Production"
        ]
        * 100
    )

    result["Quality %"] = (
        100 -
        result["Error %"]
    )

    # Prevent negative quality
    result["Quality %"] = (
        result["Quality %"]
        .clip(
            lower=0,
            upper=100
        )
    )

    # --------------------------------------------------------
    # Round calculated values
    # --------------------------------------------------------

    result["Productivity"] = (
        result["Productivity"]
        .round(2)
    )

    result["Error %"] = (
        result["Error %"]
        .round(2)
    )

    result["Quality %"] = (
        result["Quality %"]
        .round(2)
    )

    result["Period Target"] = (
        result["Period Target"]
        .round(2)
    )

    return result.reset_index(
        drop=True
    )


# ============================================================
# SAVE PROCESSED DATA
# ============================================================

def save_processed_data():

    df = build_employee_performance()

    if df.empty:

        print(
            "No employee performance data found."
        )

        return

    conn = get_connection()

    try:

        # ----------------------------------------------------
        # Save complete employee summary
        # ----------------------------------------------------

        df.to_sql(
            "employee_summary",
            conn,
            if_exists="replace",
            index=False
        )

        # ----------------------------------------------------
        # Save production summary
        # ----------------------------------------------------

        production_summary = df[
            [
                "User Name",
                "User ID's",
                "Total Production"
            ]
        ].copy()

        production_summary.to_sql(
            "production",
            conn,
            if_exists="replace",
            index=False
        )

        # ----------------------------------------------------
        # Save errors summary
        # ----------------------------------------------------

        error_summary = df[
            [
                "User Name",
                "Total Errors"
            ]
        ].copy()

        error_summary.to_sql(
            "errors",
            conn,
            if_exists="replace",
            index=False
        )

        conn.commit()

        print(
            f"Processed {len(df)} employees."
        )

        print(
            "Employee summary saved."
        )

        print(
            "Production summary saved."
        )

        print(
            "Error summary saved."
        )

    except Exception as e:

        conn.rollback()

        print(
            f"Database processing error: {e}"
        )

    finally:

        conn.close()


# ============================================================
# DISPLAY SUMMARY
# ============================================================

def show_summary():

    df = build_employee_performance()

    if df.empty:

        print(
            "No data available."
        )

        return

    print(
        "\n========================================"
    )

    print(
        "EMPLOYEE PERFORMANCE SUMMARY"
    )

    print(
        "========================================"
    )

    print(
        f"Employees: {len(df)}"
    )

    print(
        f"Total Production: "
        f"{df['Total Production'].sum():,.0f}"
    )

    print(
        f"Total Errors: "
        f"{df['Total Errors'].sum():,.0f}"
    )

    print(
        f"Average Productivity: "
        f"{df['Productivity'].mean():.2f}%"
    )

    print(
        f"Average Quality: "
        f"{df['Quality %'].mean():.2f}%"
    )

    print(
        "\nTop performers:"
    )

    top = (
        df.sort_values(
            "Productivity",
            ascending=False
        )
        .head(5)
    )

    for index, row in top.iterrows():

        print(
            f"{index + 1}. "
            f"{row['User Name']} - "
            f"{row['Productivity']:.2f}%"
        )

    print(
        "========================================\n"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "\nStarting data processing..."
    )

    save_processed_data()

    show_summary()

    print(
        "Data processing completed."
    )