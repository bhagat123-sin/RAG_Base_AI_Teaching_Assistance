import re
import unicodedata
import pymysql
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from flask_bcrypt import Bcrypt
from db import get_db_connection

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "11111111", "password", "password1",
    "password123", "qwerty123", "qwertyuiop", "iloveyou", "admin123", "welcome1",
    "abc12345", "letmein123",
}


def password_problem(password, email="", first="", last=""):
    """Returns an error message, or None if the password is acceptable."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password.encode("utf-8")) > 72:
        return "Password is too long (maximum 72 bytes)."
    if re.search(r"\s", password):
        return "Password cannot contain spaces."
    if not re.search(r"[a-z]", password):
        return "Password needs at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return "Password needs at least one uppercase letter."
    if not re.search(r"\d", password):
        return "Password needs at least one number."
    if not re.search(r"[^A-Za-z0-9\s]", password):
        return "Password needs at least one special character (for example ! @ # $ %)."
    if password.lower() in COMMON_PASSWORDS:
        return "This password is too common. Please choose a stronger one."
    lowered = password.lower()
    for part in (email.split("@")[0], first, last):
        part = part.lower().replace(" ", "")
        if len(part) >= 4 and part in lowered:
            return "Password should not contain your name or email."
    return None

def clean_name(value):
    return " ".join(str(value or "").split())  # extra spaces hata deta hai


def valid_name(value, required):
    if not value:
        return not required
    if len(value) > 50:
        return False
    # letters aur matras (Hindi naam bhi chalenge), space . ' - allowed
    has_letter = any(unicodedata.category(c)[0] == "L" for c in value)
    all_ok = all(unicodedata.category(c)[0] in ("L", "M") or c in " .'-" for c in value)
    return has_letter and all_ok


def fail(message, code=400):
    return jsonify({"error": message}), code


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.get_json(silent=True) or {}
    first = clean_name(data.get("first_name"))
    middle = clean_name(data.get("middle_name"))
    last = clean_name(data.get("last_name"))
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")           # passwords are NOT stripped
    confirm = str(data.get("confirm_password") or "")

    if not valid_name(first, True):
        return fail("Please enter a valid first name.")
    if not valid_name(middle, False):
        return fail("Middle name can only contain letters.")
    if not valid_name(last, True):
        return fail("Please enter a valid last name.")
    if len(email) > 255 or not EMAIL_RE.match(email):
        return fail("Please enter a valid email address.")

    problem = password_problem(password, email, first, last)
    if problem:
        return fail(problem)
    if password != confirm:
        return fail("Passwords do not match.")

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (first_name, middle_name, last_name, email, password_hash) "
                "VALUES (%s, %s, %s, %s, %s)",
                (first, middle or None, last, email, hashed),
            )
        conn.commit()
    except pymysql.err.IntegrityError:
        return fail("An account with this email already exists.", 409)
    except Exception as e:
        print("signup error:", repr(e))
        return fail("Something went wrong. Please try again.", 500)
    finally:
        conn.close()

    return jsonify({"message": "Account created! Please log in."})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json(silent=True) or {}
    # box mein email likhna hai; purane accounts apna purana username bhi daal sakte hain
    identifier = str(data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()

    if not identifier or not password:
        return fail("Email aur password dono zaroori hain.")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE email = %s OR username = %s",
                (identifier.lower(), identifier),
            )
            user = cursor.fetchone()
    finally:
        conn.close()

    if not user or not bcrypt.check_password_hash(user["password_hash"], password):
        return fail("Email ya password galat hai.", 401)

    session["user_id"] = user["id"]
    # sidebar mein jo naam dikhta hai wahi key; ab first name dikhega
    session["username"] = user.get("first_name") or user.get("username") or "User"

    return jsonify({"message": "Login successful!"})


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))