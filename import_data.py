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
# PRODUCTION DATA IMPORT
# ============================================================

def import_production():

    print("\nLoading production Excel...")

    if not os.path.exists(
        PRODUCTION_FILE
    ):

        print(
            "Production Excel not found:"
        )

        print(
            PRODUCTION_FILE
        )

        return

    try:

        df = pd.read_excel(
            PRODUCTION_FILE,
            sheet_name="Production"
        )

        df = df.dropna(
            how="all"
        )

        print(
            f"Production rows found: {len(df)}"
        )

        # ----------------------------------------------------
        # Save complete raw production data
        # ----------------------------------------------------

        conn = get_connection()

        df.to_sql(
            "production_data",
            conn,
            if_exists="replace",
            index=False
        )

        conn.commit()

        conn.close()

        print(
            "Production data imported successfully."
        )

    except Exception as e:

        print(
            f"Production import error: {e}"
        )


# ============================================================
# ERROR DATA IMPORT
# ============================================================

def import_errors():

    print("\nLoading error Excel...")

    if not os.path.exists(
        ERROR_FILE
    ):

        print(
            "Error Excel not found:"
        )

        print(
            ERROR_FILE
        )

        return

    try:

        # Excel first row is title row
        # Actual headers are on row 2
        df = pd.read_excel(
            ERROR_FILE,
            header=1
        )

        df = df.dropna(
            how="all"
        )

        print(
            f"Error rows found: {len(df)}"
        )

        # ----------------------------------------------------
        # Save complete raw error data
        # ----------------------------------------------------

        conn = get_connection()

        df.to_sql(
            "error_data",
            conn,
            if_exists="replace",
            index=False
        )

        conn.commit()

        conn.close()

        print(
            "Error data imported successfully."
        )

    except Exception as e:

        print(
            f"Error data import error: {e}"
        )


# ============================================================
# CREATE USERS
# ============================================================

def create_users():

    print(
        "\nCreating login users..."
    )

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # Admin
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT OR IGNORE INTO users
            (
                username,
                password,
                role
            )
            VALUES
            (
                ?,
                ?,
                ?
            )
            """,
            (
                "admin",
                "admin123",
                "admin"
            )
        )

        # ----------------------------------------------------
        # Employee
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT OR IGNORE INTO users
            (
                username,
                password,
                role
            )
            VALUES
            (
                ?,
                ?,
                ?
            )
            """,
            (
                "employee",
                "employee123",
                "employee"
            )
        )

        conn.commit()

        print(
            "Default users created."
        )

    except Exception as e:

        print(
            f"User creation error: {e}"
        )

    finally:

        conn.close()


# ============================================================
# CREATE REQUIRED TABLES
# ============================================================

def create_tables():

    print(
        "\nChecking database tables..."
    )

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # Users
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
            """
        )

        # ----------------------------------------------------
        # Employees
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employees
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                user_id TEXT,
                schedule TEXT,
                location TEXT,
                target REAL
            )
            """
        )

        # ----------------------------------------------------
        # Production
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS production
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                user_id TEXT,
                total_production REAL DEFAULT 0
            )
            """
        )

        # ----------------------------------------------------
        # Errors
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS errors
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                total_errors REAL DEFAULT 0
            )
            """
        )

        # ----------------------------------------------------
        # Employee Summary
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_summary
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                user_id TEXT,
                schedule TEXT,
                location TEXT,
                target REAL DEFAULT 0,
                total_production REAL DEFAULT 0,
                total_errors REAL DEFAULT 0
            )
            """
        )

        conn.commit()

        print(
            "Database tables checked."
        )

    except Exception as e:

        conn.rollback()

        print(
            f"Table creation error: {e}"
        )

    finally:

        conn.close()


# ============================================================
# CREATE EMPLOYEE SUMMARY
# ============================================================

def create_employee_summary():

    print(
        "\nBuilding employee summary..."
    )

    if not os.path.exists(
        PRODUCTION_FILE
    ):

        print(
            "Production Excel not found."
        )

        return

    try:

        production_df = pd.read_excel(
            PRODUCTION_FILE,
            sheet_name="Production"
        )

        production_df = production_df.dropna(
            how="all"
        )

        # ----------------------------------------------------
        # Find columns
        # ----------------------------------------------------

        name_column = None
        id_column = None
        target_column = None

        for column in production_df.columns:

            column_name = str(
                column
            ).strip().lower()

            if column_name in [
                "user name",
                "username"
            ]:

                name_column = column

            elif column_name in [
                "user id's",
                "user id",
                "employee id"
            ]:

                id_column = column

            elif column_name in [
                "target",
                "daily target"
            ]:

                target_column = column

        if name_column is None:

            print(
                "User Name column not found."
            )

            return

        # ----------------------------------------------------
        # Remove blank employees
        # ----------------------------------------------------

        production_df = production_df[
            production_df[name_column]
            .notna()
        ].copy()

        production_df[name_column] = (
            production_df[name_column]
            .astype(str)
            .str.strip()
        )

        production_df = production_df[
            production_df[name_column] != ""
        ]

        # ----------------------------------------------------
        # Find TOTAL column
        # ----------------------------------------------------

        total_column = None

        for column in production_df.columns:

            if str(column).strip().lower() == "total":

                total_column = column
                break

        # ----------------------------------------------------
        # Build summary
        # ----------------------------------------------------

        summary = pd.DataFrame()

        summary["user_name"] = (
            production_df[name_column]
        )

        if id_column:

            summary["user_id"] = (
                production_df[id_column]
            )

        else:

            summary["user_id"] = ""

        if target_column:

            summary["target"] = (
                pd.to_numeric(
                    production_df[target_column],
                    errors="coerce"
                )
                .fillna(0)
            )

        else:

            summary["target"] = 0

        if total_column:

            summary["total_production"] = (
                pd.to_numeric(
                    production_df[total_column],
                    errors="coerce"
                )
                .fillna(0)
            )

        else:

            summary["total_production"] = 0

        # ----------------------------------------------------
        # Schedule
        # ----------------------------------------------------

        if "Schedule" in production_df.columns:

            summary["schedule"] = (
                production_df["Schedule"]
            )

        else:

            summary["schedule"] = "-"

        # ----------------------------------------------------
        # Location
        # ----------------------------------------------------

        if "Location" in production_df.columns:

            summary["location"] = (
                production_df["Location"]
            )

        else:

            summary["location"] = "-"

        # ----------------------------------------------------
        # Error data
        # ----------------------------------------------------

        error_df = None

        if os.path.exists(
            ERROR_FILE
        ):

            error_df = pd.read_excel(
                ERROR_FILE,
                header=1
            )

            error_df = error_df.dropna(
                how="all"
            )

        if error_df is not None and not error_df.empty:

            error_name_column = None

            for column in error_df.columns:

                column_name = str(
                    column
                ).strip().lower()

                if column_name in [
                    "username",
                    "user name"
                ]:

                    error_name_column = column
                    break

            grand_total_column = None

            for column in error_df.columns:

                if (
                    str(column)
                    .strip()
                    .lower()
                    == "grand total"
                ):

                    grand_total_column = column
                    break

            if (
                error_name_column
                and grand_total_column
            ):

                error_summary = pd.DataFrame()

                error_summary["user_name"] = (
                    error_df[
                        error_name_column
                    ]
                    .astype(str)
                    .str.strip()
                )

                error_summary["total_errors"] = (
                    pd.to_numeric(
                        error_df[
                            grand_total_column
                        ],
                        errors="coerce"
                    )
                    .fillna(0)
                )

                summary = summary.merge(
                    error_summary,
                    on="user_name",
                    how="left"
                )

            else:

                summary["total_errors"] = 0

        else:

            summary["total_errors"] = 0

        summary["total_errors"] = (
            pd.to_numeric(
                summary["total_errors"],
                errors="coerce"
            )
            .fillna(0)
        )

        # ----------------------------------------------------
        # Save summary
        # ----------------------------------------------------

        conn = get_connection()

        summary.to_sql(
            "employee_summary",
            conn,
            if_exists="replace",
            index=False
        )

        conn.commit()

        conn.close()

        print(
            f"Employee summary created: "
            f"{len(summary)} employees"
        )

    except Exception as e:

        print(
            f"Summary creation error: {e}"
        )


# ============================================================
# MAIN IMPORT
# ============================================================

def main():

    print(
        "\n========================================"
    )

    print(
        "       EMP TRACKER DATA IMPORT"
    )

    print(
        "========================================"
    )

    create_tables()

    import_production()

    import_errors()

    create_employee_summary()

    create_users()

    print(
        "\n========================================"
    )

    print(
        "       DATA IMPORT COMPLETED"
    )

    print(
        "========================================\n"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()