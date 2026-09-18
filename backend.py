from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# --------------------------------------------------
# DATABASE PATH
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "medalert.db")


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------
# CREATE DATABASE TABLES
# --------------------------------------------------

def init_db():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symptoms TEXT NOT NULL,
            result TEXT,
            urgency TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS emergency_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            latitude REAL,
            longitude REAL,
            message TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("medalert.html")


# --------------------------------------------------
# SIGNUP
# --------------------------------------------------

@app.route("/api/signup", methods=["POST"])
def signup():

    try:

        data = request.get_json(silent=True)

        print("SIGNUP DATA:", data)

        if not data:
            return jsonify({
                "success": False,
                "message": "No signup data received"
            }), 400

        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))

        if not name:
            return jsonify({
                "success": False,
                "message": "Name is required"
            }), 400

        if not email:
            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400

        if not password:
            return jsonify({
                "success": False,
                "message": "Password is required"
            }), 400

        if len(password) < 6:
            return jsonify({
                "success": False,
                "message": "Password must contain at least 6 characters"
            }), 400

        conn = get_db()

        # Check whether email already exists
        existing_user = conn.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(TRIM(email)) = ?
            """,
            (email,)
        ).fetchone()

        if existing_user:

            conn.close()

            return jsonify({
                "success": False,
                "message": "Email already registered"
            }), 409

        # Create account
        cursor = conn.execute(
            """
            INSERT INTO users
            (name, email, password, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                password,
                datetime.now().isoformat()
            )
        )

        conn.commit()

        user_id = cursor.lastrowid

        conn.close()

        print("ACCOUNT CREATED:", email, "ID:", user_id)

        return jsonify({
            "success": True,
            "message": "Account created successfully",
            "user": {
                "id": user_id,
                "name": name,
                "email": email
            }
        })

    except Exception as e:

        print("SIGNUP ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Signup error: " + str(e)
        }), 500


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["POST"])
def login():

    try:

        data = request.get_json(silent=True)

        print("----------------------------------------")
        print("LOGIN REQUEST")
        print("DATA:", data)

        if not data:

            print("ERROR: No JSON data")

            return jsonify({
                "success": False,
                "message": "No login data received"
            }), 400

        email = str(
            data.get("email", "")
        ).strip().lower()

        password = str(
            data.get("password", "")
        )

        print("EMAIL:", email)
        print("PASSWORD RECEIVED:", bool(password))

        if not email or not password:

            return jsonify({
                "success": False,
                "message": "Email and password are required"
            }), 400

        conn = get_db()

        user = conn.execute(
            """
            SELECT id, name, email, password
            FROM users
            WHERE LOWER(TRIM(email)) = ?
            LIMIT 1
            """,
            (email,)
        ).fetchone()

        conn.close()

        print("USER FOUND:", user is not None)

        if user is None:

            print("LOGIN FAILED: USER NOT FOUND")

            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        stored_password = str(
            user["password"]
        )

        print(
            "PASSWORD MATCH:",
            stored_password == password
        )

        if stored_password != password:

            print("LOGIN FAILED: WRONG PASSWORD")

            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        print("LOGIN SUCCESS:", email)
        print("----------------------------------------")

        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        })

    except Exception as e:

        print("LOGIN ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Login error: " + str(e)
        }), 500


# --------------------------------------------------
# GET USER
# --------------------------------------------------

@app.route("/api/user/<int:user_id>", methods=["GET"])
def get_user(user_id):

    conn = get_db()

    user = conn.execute(
        """
        SELECT id, name, email, created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()

    if not user:

        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404

    return jsonify({
        "success": True,
        "user": dict(user)
    })


# --------------------------------------------------
# AI ASSESSMENT
# --------------------------------------------------

@app.route("/api/assessment", methods=["POST"])
def assessment():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid JSON data"
        }), 400

    user_id = data.get("user_id")

    symptoms = str(
        data.get("symptoms", "")
    ).strip()

    if not symptoms:

        return jsonify({
            "success": False,
            "message": "Please enter symptoms"
        }), 400

    symptoms_lower = symptoms.lower()

    emergency_words = [
        "chest pain",
        "difficulty breathing",
        "shortness of breath",
        "unconscious",
        "severe bleeding",
        "stroke",
        "heart attack",
        "seizure"
    ]

    urgent_words = [
        "high fever",
        "vomiting",
        "severe pain",
        "dizziness",
        "fainting"
    ]

    if any(
        word in symptoms_lower
        for word in emergency_words
    ):

        urgency = "Emergency"

        result = (
            "Immediate medical attention is recommended."
        )

    elif any(
        word in symptoms_lower
        for word in urgent_words
    ):

        urgency = "Urgent"

        result = (
            "Medical evaluation should be considered soon."
        )

    else:

        urgency = "Low"

        result = (
            "Monitor the symptoms and consult a healthcare "
            "professional if they continue or worsen."
        )

    conn = get_db()

    conn.execute(
        """
        INSERT INTO assessments
        (user_id, symptoms, result, urgency, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            symptoms,
            result,
            urgency,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "urgency": urgency,
        "result": result,
        "disclaimer": (
            "This is a prototype decision-support result "
            "and is not a medical diagnosis."
        )
    })


# --------------------------------------------------
# ASSESSMENT HISTORY
# --------------------------------------------------

@app.route(
    "/api/assessment/<int:user_id>",
    methods=["GET"]
)
def assessment_history(user_id):

    conn = get_db()

    records = conn.execute(
        """
        SELECT id, symptoms, result, urgency, created_at
        FROM assessments
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "assessments": [
            dict(record)
            for record in records
        ]
    })


# --------------------------------------------------
# EMERGENCY ALERT
# --------------------------------------------------

@app.route(
    "/api/emergency-alert",
    methods=["POST"]
)
def emergency_alert():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid JSON data"
        }), 400

    user_id = data.get("user_id")
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    message = data.get(
        "message",
        "Emergency assistance required"
    )

    conn = get_db()

    conn.execute(
        """
        INSERT INTO emergency_alerts
        (user_id, latitude, longitude, message, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            latitude,
            longitude,
            message,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Emergency alert recorded",
        "location": {
            "latitude": latitude,
            "longitude": longitude
        }
    })


# --------------------------------------------------
# EMERGENCY HISTORY
# --------------------------------------------------

@app.route(
    "/api/emergency-alert/<int:user_id>",
    methods=["GET"]
)
def emergency_history(user_id):

    conn = get_db()

    alerts = conn.execute(
        """
        SELECT *
        FROM emergency_alerts
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "success": True,
        "alerts": [
            dict(alert)
            for alert in alerts
        ]
    })


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

init_db()

if __name__ == "__main__":

    print("----------------------------------------")
    print("MedAlert AI Backend")
    print("http://127.0.0.1:5000")
    print("----------------------------------------")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )