import sqlite3
import os
from flask import Flask, request, render_template_string, redirect, url_for, session

app = Flask(__name__)

# B105: hardcoded secret key
app.secret_key = "supersecretkey123"

# B105: hardcoded database password (not used for sqlite but flagged by Bandit)
DB_PASSWORD = "admin1234"
DB_PATH = "users.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT
        )
    """)
    conn.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'admin', 'password123')")
    conn.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (2, 'alice', 'alice456')")
    conn.commit()
    conn.close()


LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
  <h2>Login</h2>
  {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
  <form method="POST">
    <label>Username: <input name="username" type="text"/></label><br><br>
    <label>Password: <input name="password" type="password"/></label><br><br>
    <input type="submit" value="Login"/>
  </form>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
  <h2>Welcome, {{ username }}!</h2>
  <p><a href="/calc">Calculator</a> | <a href="/logout">Logout</a></p>
</body>
</html>
"""

CALC_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Calculator</title></head>
<body>
  <h2>Calculator</h2>
  {% if result is not none %}<p>Result: {{ result }}</p>{% endif %}
  <form method="POST">
    <label>Expression: <input name="expr" type="text" placeholder="e.g. 2+2"/></label>
    <input type="submit" value="Calculate"/>
  </form>
  <p><a href="/">Home</a></p>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # B608: SQL injection via string concatenation
        query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
        conn = get_db()
        cursor = conn.execute(query)
        user = cursor.fetchone()
        conn.close()

        if user:
            session["username"] = username
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid credentials"

    return render_template_string(LOGIN_TEMPLATE, error=error)


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template_string(DASHBOARD_TEMPLATE, username=session["username"])


@app.route("/calc", methods=["GET", "POST"])
def calc():
    result = None
    if request.method == "POST":
        expr = request.form.get("expr", "")
        # B307: use of eval() on user input
        try:
            result = eval(expr)
        except Exception as e:
            result = f"Error: {e}"
    return render_template_string(CALC_TEMPLATE, result=result)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    # B201: Flask app running with debug=True
    app.run(host="0.0.0.0", port=5000, debug=True)
