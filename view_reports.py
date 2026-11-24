import sqlite3

conn = sqlite3.connect("civiclens.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM reports")
reports = cursor.fetchall()

for report in reports:
    print(report)

conn.close()
