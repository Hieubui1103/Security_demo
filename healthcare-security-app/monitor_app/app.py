from flask import Flask, render_template, jsonify
import sqlite3
import pandas as pd
import re
from datetime import datetime

app = Flask(__name__)

def detect_anomalies():
    conn = sqlite3.connect("../healthcare.db")
    logs_df = pd.read_sql_query("SELECT * FROM access_logs", conn)
    conn.close()

    if logs_df.empty:
        return []

    logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
    logs_df['hour'] = logs_df['timestamp'].dt.hour

    def detect_high_access(df, threshold=20, window_seconds=30):
        df = df.sort_values(by=['user_id', 'user_role', 'timestamp'])
        results = []
        for (user_id, user_role), group in df.groupby(['user_id', 'user_role']):
            timestamps = group['timestamp'].tolist()
            for i in range(len(timestamps)):
                window_start = timestamps[i]
                window_end = window_start + pd.Timedelta(seconds=window_seconds)
                count = sum((ts >= window_start and ts <= window_end) for ts in timestamps)
                if count > threshold:
                    results.append({
                        "timestamp": window_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "high_access": f"User {user_id} ({user_role}) accessed {count} records within {window_seconds}s.",
                        "off_hour": ""
                    })
                    break
        return results

    def detect_off_hours(df):
        results = []
        off_hours = df[(df['hour'] < 9) | (df['hour'] > 17)]
        for _, row in off_hours.iterrows():
            results.append({
                "timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "high_access": "",
                "off_hour": f"User {row.user_id} accessed patient {row.patient_id}."
            })
        return results

    high_access_alerts = detect_high_access(logs_df)
    off_hour_alerts = detect_off_hours(logs_df)

    # Combine and sort all alerts by timestamp (latest first)
    all_alerts = high_access_alerts + off_hour_alerts
    all_alerts.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_alerts

def extract_timestamp(alert):
    # Try to find a timestamp in the alert string
    match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', alert)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    else:
        return datetime.min  # fallback for alerts without timestamp
    
def clear_access_logs():
    conn = sqlite3.connect("../healthcare.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM access_logs")
    conn.commit()
    conn.close()

@app.route("/")
def dashboard():
    clear_access_logs()  # Clear logs every time the dashboard is loaded
    return render_template("dashboard.html")

@app.route("/alerts")
def alerts():
    return jsonify(detect_anomalies())

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)