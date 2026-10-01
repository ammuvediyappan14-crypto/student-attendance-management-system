from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = "attendance.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin'
    );
    CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        year TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        att_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
        UNIQUE(student_id, att_date),
        FOREIGN KEY(student_id) REFERENCES students(id)
    );
    """)
    if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        conn.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                     ("admin","admin123","admin"))
    conn.commit()
    conn.close()

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?",
                            (username,password)).fetchone()
        conn.close()
        if user:
            session["user"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect(url_for("login"))
    conn = get_db()
    total_students = conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
    today = date.today().isoformat()
    present = conn.execute("SELECT COUNT(*) c FROM attendance WHERE att_date=? AND status='Present'", (today,)).fetchone()["c"]
    absent = conn.execute("SELECT COUNT(*) c FROM attendance WHERE att_date=? AND status='Absent'", (today,)).fetchone()["c"]
    conn.close()
    return render_template("dashboard.html", total_students=total_students, present=present, absent=absent, today=today)

@app.route("/students", methods=["GET","POST"])
def students():
    if "user" not in session: return redirect(url_for("login"))
    conn = get_db()
    if request.method == "POST":
        try:
            conn.execute("INSERT INTO students(roll_no,name,department,year) VALUES(?,?,?,?)",
                         (request.form["roll_no"], request.form["name"], request.form["department"], request.form["year"]))
            conn.commit()
            flash("Student added successfully", "success")
        except sqlite3.IntegrityError:
            flash("Roll number already exists", "danger")
    rows = conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    conn.close()
    return render_template("students.html", students=rows)

@app.route("/students/delete/<int:student_id>")
def delete_student(student_id):
    if "user" not in session: return redirect(url_for("login"))
    conn = get_db()
    conn.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("students"))

@app.route("/attendance", methods=["GET","POST"])
def attendance():
    if "user" not in session: return redirect(url_for("login"))
    selected_date = request.values.get("att_date", date.today().isoformat())
    conn = get_db()
    students = conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    if request.method == "POST":
        for s in students:
            status = request.form.get(f"status_{s['id']}", "Absent")
            conn.execute("""INSERT INTO attendance(student_id,att_date,status)
                            VALUES(?,?,?)
                            ON CONFLICT(student_id,att_date) DO UPDATE SET status=excluded.status""",
                         (s["id"], selected_date, status))
        conn.commit()
        flash("Attendance saved successfully", "success")
    existing = {r["student_id"]: r["status"] for r in conn.execute(
        "SELECT student_id,status FROM attendance WHERE att_date=?", (selected_date,)).fetchall()}
    conn.close()
    return render_template("attendance.html", students=students, selected_date=selected_date, existing=existing)

@app.route("/reports")
def reports():
    if "user" not in session: return redirect(url_for("login"))
    conn = get_db()
    rows = conn.execute("""
      SELECT s.id,s.roll_no,s.name,s.department,s.year,
             SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) present,
             COUNT(a.id) total
      FROM students s LEFT JOIN attendance a ON s.id=a.student_id
      GROUP BY s.id ORDER BY s.roll_no
    """).fetchall()
    conn.close()
    return render_template("reports.html", rows=rows)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
