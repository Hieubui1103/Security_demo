from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="../.env")
print("Loaded AUTH_KEY:", os.getenv("AUTH_KEY"))
app = Flask(__name__)
app.secret_key = "your_secret_key"

def valid_user_id(user_id, user_role):
    try:
        user_id_int = int(user_id)
    except ValueError:
        return False
    if user_role == "nurse":
        return 0 <= user_id_int <= 2999
    elif user_role == "doctor":
        return 3000 <= user_id_int <= 4999
    elif user_role == "admin":
        return 5000 <= user_id_int <= 6999
    elif user_role == "researcher":
        return 7000 <= user_id_int <= 9999
    return False

def get_patient_data(full_access=False, patient_id=None):
    conn = sqlite3.connect("../healthcare.db")
    if full_access:
        query = "SELECT * FROM patients WHERE patient_id = ?" if patient_id else "SELECT * FROM patients"
    else:
        query = "SELECT * FROM redacted_patients WHERE patient_id = ?" if patient_id else "SELECT * FROM redacted_patients"
    if patient_id:
        df = pd.read_sql_query(query, conn, params=(patient_id,))
    else:
        df = pd.read_sql_query(query, conn)
    access_type = "Full" if full_access else "Redacted"
    conn.close()
    return df, access_type

def verify_user_access(user_id, user_role):
    try:
        user_id = int(user_id)
    except:
        return False
    valid_roles = ["doctor", "admin"]
    doctor_id = 3000 <= user_id <= 4999
    admin_id = 5000 <= user_id <= 6999
    return user_role in valid_roles and (doctor_id or admin_id)

def log_access(user_id, user_role, action, patient_id, access_range):
    conn = sqlite3.connect("../healthcare.db")
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO access_logs (user_id, user_role, timestamp, action, patient_id, access_range)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, user_role, timestamp, action, patient_id, access_range))
    conn.commit()
    conn.close()

@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    user_id = ""
    user_role = ""
    action = ""
    patient_id = ""
    full_access = session.get("full_access", False)
    signed_in_role = session.get("user_role")
    signed_in_id = session.get("user_id")
    if request.method == "POST":
        if full_access and signed_in_id and signed_in_role:
            user_id = signed_in_id
            user_role = signed_in_role
        else:
            user_id = request.form.get("user_id", "")
            user_role = request.form.get("user_role", "")
        action = request.form.get("action", "")
        patient_id = request.form.get("patient_id", "")
        # Validate user_id
        if not valid_user_id(user_id, user_role):
            error = "Invalid User ID for the selected role. Please rewrite it."
        else:
            # Validate patient_id
            try:
                patient_id_int = int(patient_id)
                if not (1 <= patient_id_int <= 100):
                    raise ValueError
            except ValueError:
                error = "Patient ID must be between 1 and 100."
            else:
                access_range = "full" if full_access else "limited"
                log_access(
                    user_id,
                    signed_in_role if full_access else user_role,
                    action,
                    patient_id,
                    access_range
                )
                df, access_type = get_patient_data(full_access=full_access, patient_id=patient_id)
                data = df.to_html(classes="table table-striped", index=False)
                return render_template(
                    "index.html",
                    data=data,
                    access_type=access_type,
                    error=error,
                    user_id=user_id,
                    user_role=user_role,
                    action=action,
                    patient_id=patient_id,
                    authenticated=full_access,
                    signed_in_role=signed_in_role,
                )
    # GET or error: show nothing or empty table
    data = ""
    access_type = "Full" if full_access else "Redacted"
    return render_template(
        "index.html",
        data=data,
        access_type=access_type,
        error=error,
        user_id=user_id,
        user_role=user_role,
        action=action,
        patient_id=patient_id,
        authenticated=full_access,
        signed_in_role=signed_in_role,
        signed_in_id=signed_in_id
    )

@app.route("/login", methods=["POST"])
def login():
    user_id = request.form.get("user_id")
    user_role = request.form.get("user_role")
    auth_key = request.form.get("auth_key")
    # For demonstration, let's use a simple static key check
    if not auth_key or auth_key != os.getenv("AUTH_KEY"):
        return jsonify({"success": False, "message": "Invalid authentication key."})
    if verify_user_access(user_id, user_role):
        session["full_access"] = True
        session["user_role"] = user_role
        session["user_id"] = user_id
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Invalid credentials. Please try again."})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/simulate_high_access", methods=["POST"])
def simulate_high_access():
    conn = sqlite3.connect("../healthcare.db")
    cursor = conn.cursor()
    current_time = datetime.now()
    if random.choice(["doctor", "admin"]) == "doctor":
        user_id = str(random.randint(3000, 4999))
        user_role = "doctor"
    else:
        user_id = str(random.randint(5000, 6999))
        user_role = "admin"

    for _ in range(60):
        time_increment = timedelta(seconds=random.uniform(0.5, 1.5))
        current_time += time_increment
        timestamp = current_time.replace(hour=10, minute=19).strftime("%Y-%m-%d %H:%M:%S")
        action = "read"
        patient_id = random.randint(1, 100)
        access_range = "full"
        cursor.execute("""
            INSERT INTO access_logs (user_id, user_role, timestamp, action, patient_id, access_range)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, user_role, timestamp, action, patient_id, access_range))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "High access anomaly simulated."})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)