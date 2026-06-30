from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "student_performance_analyzer_secret_key"

DB_NAME = "database.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            marks1 INTEGER DEFAULT 0,
            marks2 INTEGER DEFAULT 0,
            marks3 INTEGER DEFAULT 0,
            attendance REAL DEFAULT 0
        )
    """)

    cur.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "admin123", "faculty"),
        )

    conn.commit()
    conn.close()


def calculate_performance(marks1, marks2, marks3, attendance):
    total = marks1 + marks2 + marks3
    average = total / 3
    percentage = (total / 300) * 100

    if average >= 90:
        grade = "A"
    elif average >= 75:
        grade = "B"
    elif average >= 60:
        grade = "C"
    elif average >= 40:
        grade = "D"
    else:
        grade = "Fail"

    at_risk = average < 40 or attendance < 75
    status = "At Risk" if at_risk else "Good"

    return {
        "total": total,
        "average": round(average, 2),
        "percentage": round(percentage, 2),
        "grade": grade,
        "at_risk": at_risk,
        "status": status,
    }


@app.route("/")
def index():
    if "username" in session:
        if session["role"] == "faculty":
            return redirect(url_for("faculty_dashboard"))
        else:
            return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        user = cur.fetchone()
        conn.close()

        if user:
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Login successful!", "success")
            if user["role"] == "faculty":
                return redirect(url_for("faculty_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/faculty")
def faculty_dashboard():
    if "username" not in session or session.get("role") != "faculty":
        flash("Access denied. Please log in as faculty.", "danger")
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()

    conn = get_db()
    cur = conn.cursor()

    if search:
        cur.execute(
            "SELECT * FROM students WHERE name LIKE ? ORDER BY name",
            (f"%{search}%",),
        )
    else:
        cur.execute("SELECT * FROM students ORDER BY name")

    rows = cur.fetchall()
    conn.close()

    students = []
    at_risk_students = []
    total_percentage = 0

    for row in rows:
        perf = calculate_performance(
            row["marks1"], row["marks2"], row["marks3"], row["attendance"]
        )
        student = dict(row)
        student.update(perf)
        students.append(student)
        total_percentage += perf["percentage"]
        if perf["at_risk"]:
            at_risk_students.append(student)

    total_students = len(students)
    avg_class_performance = (
        round(total_percentage / total_students, 2) if total_students > 0 else 0
    )

    return render_template(
        "faculty_dashboard.html",
        students=students,
        at_risk_students=at_risk_students,
        total_students=total_students,
        at_risk_count=len(at_risk_students),
        avg_class_performance=avg_class_performance,
        search=search,
    )


@app.route("/faculty/add", methods=["POST"])
def add_student():
    if "username" not in session or session.get("role") != "faculty":
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    marks1 = int(request.form.get("marks1", 0))
    marks2 = int(request.form.get("marks2", 0))
    marks3 = int(request.form.get("marks3", 0))
    attendance = float(request.form.get("attendance", 0))

    if not name or not username or not password:
        flash("Name, username, and password are required.", "danger")
        return redirect(url_for("faculty_dashboard"))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password, "student"),
        )
        cur.execute(
            """INSERT INTO students (username, name, marks1, marks2, marks3, attendance)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, name, marks1, marks2, marks3, attendance),
        )
        conn.commit()
        flash(f"Student '{name}' added successfully.", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists. Choose a different one.", "danger")
    finally:
        conn.close()

    return redirect(url_for("faculty_dashboard"))


@app.route("/faculty/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    if "username" not in session or session.get("role") != "faculty":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        marks1 = int(request.form.get("marks1", 0))
        marks2 = int(request.form.get("marks2", 0))
        marks3 = int(request.form.get("marks3", 0))
        attendance = float(request.form.get("attendance", 0))

        cur.execute(
            """UPDATE students
               SET name = ?, marks1 = ?, marks2 = ?, marks3 = ?, attendance = ?
               WHERE id = ?""",
            (name, marks1, marks2, marks3, attendance, student_id),
        )
        conn.commit()
        conn.close()
        flash("Student updated successfully.", "success")
        return redirect(url_for("faculty_dashboard"))

    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()
    conn.close()

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("faculty_dashboard"))

    return render_template("faculty_dashboard.html", edit_student=dict(student))


@app.route("/faculty/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    if "username" not in session or session.get("role") != "faculty":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM students WHERE id = ?", (student_id,))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM users WHERE username = ?", (row["username"],))
        cur.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        flash("Student deleted.", "info")
    conn.close()

    return redirect(url_for("faculty_dashboard"))


@app.route("/student")
def student_dashboard():
    if "username" not in session or session.get("role") != "student":
        flash("Access denied. Please log in as a student.", "danger")
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE username = ?", (session["username"],))
    row = cur.fetchone()
    conn.close()

    if not row:
        flash("Student record not found.", "danger")
        return redirect(url_for("logout"))

    perf = calculate_performance(
        row["marks1"], row["marks2"], row["marks3"], row["attendance"]
    )
    student = dict(row)
    student.update(perf)

    return render_template("student_dashboard.html", student=student)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
