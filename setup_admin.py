
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("civiclens.db")

conn.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )
""")

username = input("Create admin username: ").strip()
password = getpass("Create admin password: ")
confirm_password = getpass("Confirm admin password: ")

if not username:
    print("Username cannot be empty.")

elif len(password) < 8:
    print("Password must contain at least 8 characters.")

elif password != confirm_password:
    print("Passwords do not match.")

else:
    password_hash = generate_password_hash(password)

    try:
        conn.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )

        conn.commit()
        print("Admin account created successfully!")

    except sqlite3.IntegrityError:
        print("This admin username already exists.")

conn.close()
