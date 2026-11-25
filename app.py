from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_bcrypt import Bcrypt
from process_incoming import get_answer
from auth import auth_bp, bcrypt
from db import get_db_connection

app = Flask(__name__)
app.secret_key = "this-are-secret-key"
bcrypt.init_app(app)

app.register_blueprint(auth_bp)


@app.route("/")
def landing():
    return render_template("landing.html")


def get_user_sessions(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, created_at FROM sessions WHERE user_id = %s ORDER BY id DESC",
        (user_id,)
    )
    sessions = cursor.fetchall()
    conn.close()
    return sessions


@app.route("/chat")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_sessions = get_user_sessions(session["user_id"])

    if not user_sessions:
        # koi session nahi hai, ek naya bana dete hainG
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (user_id, title) VALUES (%s, %s)",
            (session["user_id"], "Untitled study session")
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return redirect(url_for("chat_session", session_id=new_id))

    # sabse naya session khol dete hain
    return redirect(url_for("chat_session", session_id=user_sessions[0]["id"]))


@app.route("/chat/<int:session_id>")
def chat_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # verify session is user ka hi hai
    cursor.execute(
        "SELECT id FROM sessions WHERE id = %s AND user_id = %s",
        (session_id, session["user_id"])
    )
    if not cursor.fetchone():
        conn.close()
        return redirect(url_for("home"))

    cursor.execute(
        "SELECT question, answer FROM chat_history WHERE session_id = %s ORDER BY id ASC",
        (session_id,)
    )
    history = cursor.fetchall()
    conn.close()

    user_sessions = get_user_sessions(session["user_id"])

    return render_template(
        "index.html",
        username=session.get("username"),
        history=history,
        sessions=user_sessions,
        active_session_id=session_id
    )


@app.route("/session/new", methods=["POST"])
def new_session():
    if "user_id" not in session:
        return jsonify({"error": "Pehle login karein."}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (user_id, title) VALUES (%s, %s)",
        (session["user_id"], "Untitled study session")
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({"session_id": new_id})

@app.route("/session/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    if "user_id" not in session:
        return jsonify({"error": "Pehle login karein."}), 401

    uid = session["user_id"]
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # sirf apni hi chat delete ho sakti hai
            cursor.execute("SELECT id FROM sessions WHERE id = %s AND user_id = %s", (session_id, uid))
            if not cursor.fetchone():
                return jsonify({"error": "Chat not found."}), 404
            # pehle messages, phir session (foreign key ki wajah se yahi order zaroori hai)
            cursor.execute("DELETE FROM chat_history WHERE session_id = %s AND user_id = %s", (session_id, uid))
            cursor.execute("DELETE FROM sessions WHERE id = %s AND user_id = %s", (session_id, uid))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("delete_session error:", repr(e))
        return jsonify({"error": "Could not delete the chat."}), 500
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/sessions", methods=["DELETE"])
def delete_all_sessions():
    if "user_id" not in session:
        return jsonify({"error": "Pehle login karein."}), 401

    uid = session["user_id"]
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM chat_history WHERE user_id = %s", (uid,))
            cursor.execute("DELETE FROM sessions WHERE user_id = %s", (uid,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("delete_all_sessions error:", repr(e))
        return jsonify({"error": "Could not clear chats."}), 500
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/ask", methods=["POST"])
def ask():
    if "user_id" not in session:
        return jsonify({"error": "Pehle login karein."}), 401

    data = request.get_json()
    question = data.get("question", "").strip()
    session_id = data.get("session_id")

    if not question:
        return jsonify({"error": "Please ask a question."}), 400
    if not session_id:
        return jsonify({"error": "Session ID missing."}), 400

    # answer, sources = get_answer(question)
    try:
        answer, sources = get_answer(question)
    except Exception as e:
        print("get_answer error:", e)
        error_text = str(e).lower()
        if "503" in error_text or "temporarily unavailable" in error_text or "high demand" in error_text:
            return jsonify({
                "error": "AI service is busy due to high demand. Please wait a few seconds and try again."
            }), 503
        return jsonify({"error": "AI is temporarily unavailable. Please try again."}), 503

    conn = get_db_connection()
    cursor = conn.cursor()

    # agar ye session ka pehla sawaal hai, to title us sawaal se set kar dete hain
    cursor.execute("SELECT title FROM sessions WHERE id = %s", (session_id,))
    row = cursor.fetchone()
    if row and row["title"] == "Untitled study session":
        short_title = question[:40] + ("..." if len(question) > 40 else "")
        cursor.execute("UPDATE sessions SET title = %s WHERE id = %s", (short_title, session_id))

    cursor.execute(
        "INSERT INTO chat_history (user_id, session_id, question, answer) VALUES (%s, %s, %s, %s)",
        (session["user_id"], session_id, question, answer)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "answer": answer,
        "sources": sources
    })


if __name__ == "__main__":
    app.run(debug=True)