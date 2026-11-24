
import sqlite3

DATABASE_NAME = "civiclens.db"


def create_database():

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # --------------------------------
    # CITIZEN USERS TABLE
    # --------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add phone column to existing users table
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column[1] for column in cursor.fetchall()]

    if "phone" not in user_columns:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN phone TEXT
        """)

    # --------------------------------
    # COMPLAINTS TABLE
    # --------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    # --------------------------------
    # ADD USER ID TO EXISTING REPORTS
    # --------------------------------

    cursor.execute("PRAGMA table_info(reports)")
    report_columns = [column[1] for column in cursor.fetchall()]

    if "user_id" not in report_columns:
        cursor.execute("""
            ALTER TABLE reports
            ADD COLUMN user_id INTEGER
            REFERENCES users(id)
        """)

    # --------------------------------
    # NOTIFICATION HISTORY TABLE
    # --------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_database()
    print("CivicLens database updated successfully!")
