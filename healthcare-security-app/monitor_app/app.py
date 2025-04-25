from flask import Flask, render_template, jsonify
import sqlite3
import pandas as pd

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
        flagged = []
        for (user_id, user_role), group in df.groupby(['user_id', 'user_role']):
            timestamps = group['timestamp'].tolist()
            for i in range(len(timestamps)):
                window_start = timestamps[i]
                window_end = window_start + pd.Timedelta(seconds=window_seconds)
                count = sum((ts >= window_start and ts <= window_end) for ts in timestamps)
                if count > threshold:
                    flagged.append(
                        f"User {user_id} ({user_role}) accessed {count} records within {window_seconds}s starting at {window_start.strftime('%Y-%m-%d %H:%M:%S')}."
                    )
                    break
        return flagged

    def detect_off_hours(df):
        off_hours = df[(df['hour'] < 9) | (df['hour'] > 17)]
        alerts = [
            f"User {row.user_id} accessed patient {row.patient_id} at {row.timestamp} (off-hours)."
            for _, row in off_hours.iterrows()
        ]
        return alerts

    high_access_alerts = detect_high_access(logs_df)
    off_hour_alerts = detect_off_hours(logs_df)
    return high_access_alerts + off_hour_alerts

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/alerts")
def alerts():
    return jsonify(detect_anomalies())

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)