
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import secrets
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from database import create_database

app = Flask(__name__)

# --------------------------------
# SESSION SECURITY
# --------------------------------

app.secret_key = (
    os.environ.get("CIVICLENS_SECRET_KEY")
    or secrets.token_hex(32)
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("CIVICLENS_HTTPS", "false").lower() == "true"
)

create_database()


# --------------------------------
# DATABASE CONNECTION
# --------------------------------

def get_db_connection():
    conn = sqlite3.connect("civiclens.db")
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------
# ADMIN LOGIN PROTECTION
# --------------------------------

def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


# --------------------------------
# CITIZEN LOGIN PROTECTION
# --------------------------------

def citizen_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("citizen_login"))
        return function(*args, **kwargs)
    return wrapper


# --------------------------------
# CITIZEN HOME PAGE
# --------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------
# CITIZEN REGISTRATION
# --------------------------------

@app.route("/citizen/register", methods=["GET", "POST"])
def citizen_register():

    error = None

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            error = "Please fill in all required fields."

        elif len(password) < 8:
            error = "Password must contain at least 8 characters."

        elif password != confirm_password:
            error = "Passwords do not match."

        else:
            password_hash = generate_password_hash(password)
            conn = get_db_connection()

            try:
                cursor = conn.execute("""
                    INSERT INTO users (name, email, password_hash)
                    VALUES (?, ?, ?)
                """, (name, email, password_hash))

                user_id = cursor.lastrowid
                conn.commit()

                session.clear()
                session["user_id"] = user_id
                session["citizen_name"] = name
                session["citizen_email"] = email

                return redirect(url_for("report"))

            except sqlite3.IntegrityError:
                error = "This email is already registered."

            finally:
                conn.close()

    return render_template("register.html", error=error)


# --------------------------------
# CITIZEN LOGIN
# --------------------------------

@app.route("/citizen/login", methods=["GET", "POST"])
def citizen_login():

    error = None

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password_hash"], password):

            session.clear()
            session["user_id"] = user["id"]
            session["citizen_name"] = user["name"]
            session["citizen_email"] = user["email"]

            return redirect(url_for("my_complaints"))

        error = "Invalid email or password."

    return render_template("citizen_login.html", error=error)


# --------------------------------
# CITIZEN LOGOUT
# --------------------------------

@app.route("/citizen/logout")
@citizen_required
def citizen_logout():

    session.clear()
    return redirect(url_for("home"))


# --------------------------------
# COMPLAINT REPORT PAGE
# --------------------------------

@app.route("/report")
@citizen_required
def report():

    return render_template(
        "report.html",
        citizen_name=session["citizen_name"],
        citizen_email=session["citizen_email"]
    )


# --------------------------------
# SUBMIT COMPLAINT
# --------------------------------

@app.route("/submit", methods=["POST"])
@citizen_required
def submit():

    name = session["citizen_name"]
    email = session["citizen_email"]

    category = request.form.get("category", "").strip()
    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()

    if not category or not location or not description:
        return "Please fill in all complaint details.", 400

    conn = get_db_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO reports
            (name, email, category, location, description, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            category,
            location,
            description,
            session["user_id"]
        ))

        report_id = cursor.lastrowid
        conn.commit()

    finally:
        conn.close()

    return render_template("success.html", report_id=report_id)


# --------------------------------
# CITIZEN DASHBOARD
# --------------------------------

@app.route("/citizen/dashboard")
@citizen_required
def citizen_dashboard():

    conn = get_db_connection()
    user_id = session["user_id"]

    total = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE user_id = ?",
        (user_id,)
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE user_id = ? AND status = 'Pending'",
        (user_id,)
    ).fetchone()[0]

    progress = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE user_id = ? AND status = 'In Progress'",
        (user_id,)
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE user_id = ? AND status = 'Resolved'",
        (user_id,)
    ).fetchone()[0]

    conn.close()

    return render_template(
        "citizen_dashboard.html",
        citizen_name=session["citizen_name"],
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved
    )


# --------------------------------
# DASHBOARD SHORT URL
# --------------------------------

@app.route("/dashboard")
@citizen_required
def dashboard_alias():
    return redirect(url_for("citizen_dashboard"))


# --------------------------------
# CITIZEN PRIVATE COMPLAINT HISTORY
# --------------------------------

@app.route("/my-complaints")
@citizen_required
def my_complaints():

    conn = get_db_connection()

    reports = conn.execute("""
        SELECT * FROM reports
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "my_complaints.html",
        reports=reports
    )


# --------------------------------
# CITIZEN PRIVATE COMPLAINT TRACKING
# --------------------------------

@app.route("/track", methods=["GET", "POST"])
@citizen_required
def track_complaint():

    report = None
    error = None
    stage_index = 0

    if request.method == "POST":

        complaint_id = request.form.get("complaint_id", "").strip()

        if not complaint_id.isdigit():
            error = "Please enter a valid Complaint ID."

        else:
            conn = get_db_connection()

            report = conn.execute("""
                SELECT * FROM reports
                WHERE id = ? AND user_id = ?
            """, (
                int(complaint_id),
                session["user_id"]
            )).fetchone()

            conn.close()

            if report is None:
                error = "Complaint not found in your account."

            else:
                status = report["status"]

                if status == "Pending":
                    stage_index = 1
                elif status == "In Progress":
                    stage_index = 2
                elif status == "Resolved":
                    stage_index = 3

    return render_template(
        "track.html",
        report=report,
        error=error,
        stage_index=stage_index
    )


# --------------------------------
# ADMIN LOGIN
# --------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()

        admin = conn.execute(
            "SELECT * FROM admins WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password_hash"], password
        ):

            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]

            return redirect(url_for("admin_dashboard"))

        error = "Invalid username or password."

    return render_template("login.html", error=error)


# --------------------------------
# ADMIN COMPLAINT DETAILS
# --------------------------------

@app.route("/complaint/<int:report_id>")
@login_required
def complaint_details(report_id):

    conn = get_db_connection()

    report = conn.execute(
        "SELECT * FROM reports WHERE id = ?",
        (report_id,)
    ).fetchone()

    conn.close()

    if report is None:
        return "Complaint not found", 404

    return render_template(
        "complaint_details.html",
        report=report
    )


# --------------------------------
# ADMIN DASHBOARD WITH SEARCH
# AND FILTERS
# --------------------------------

@app.route("/admin")
@login_required
def admin_dashboard():

    conn = get_db_connection()

    search = request.args.get("search", "").strip()
    category_filter = request.args.get("category", "").strip()
    status_filter = request.args.get("status", "").strip()

    sql = "SELECT * FROM reports WHERE 1=1"
    params = []

    if search:
        sql += """
            AND (
                name LIKE ?
                OR email LIKE ?
                OR category LIKE ?
                OR location LIKE ?
                OR description LIKE ?
            )
        """

        keyword = f"%{search}%"
        params.extend([keyword] * 5)

    if category_filter:
        sql += " AND category = ?"
        params.append(category_filter)

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if status_filter in allowed_statuses:
        sql += " AND status = ?"
        params.append(status_filter)

    sql += " ORDER BY id DESC"

    reports = conn.execute(sql, params).fetchall()

    categories = conn.execute(
        "SELECT DISTINCT category FROM reports ORDER BY category"
    ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM reports"
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status = 'Pending'"
    ).fetchone()[0]

    progress = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status = 'In Progress'"
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status = 'Resolved'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin.html",
        reports=reports,
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved,
        search=search,
        category_filter=category_filter,
        status_filter=status_filter,
        categories=categories
    )


# --------------------------------
# ADMIN UPDATE COMPLAINT STATUS
# --------------------------------

@app.route("/update_status/<int:report_id>", methods=["POST"])
@login_required
def update_status(report_id):

    status = request.form.get("status")

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if status not in allowed_statuses:
        return "Invalid status", 400

    conn = get_db_connection()

    cursor = conn.execute(
        "UPDATE reports SET status = ? WHERE id = ?",
        (status, report_id)
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return "Complaint not found", 404

    return redirect(url_for("admin_dashboard"))


# --------------------------------
# ADMIN LOGOUT
# --------------------------------

@app.route("/logout")
@login_required
def logout():

    session.clear()
    return redirect(url_for("login"))


# --------------------------------
# RUN FLASK APPLICATION
# --------------------------------

if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    )
