from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO, emit
import random
from string import ascii_uppercase
from openai import OpenAI

from dotenv import load_dotenv
import os

load_dotenv()

OPENAIKEYNAME = os.getenv('OPENAIKEYNAME')
ASSISTANT_ID = os.getenv('ASSISTANT_ID')
print(type(ASSISTANT_ID))

app = Flask(__name__)
app.config["SECRET_KEY"] = "secretkeyname"
socketio = SocketIO(app)

client = OpenAI(api_key=OPENAIKEYNAME)
assistant_id = ASSISTANT_ID

rooms = {}

def generate_unique_code(length):
    while True:
        code = "".join(random.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            break
    return code

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)
        role = request.form.get("role")

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name, role=role)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name, role=role)

        if not role:
            return render_template("home.html", error="Please select a role.", code=code, name=name, role=role)

        room = code
        if create != False:
            room = generate_unique_code(8)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        session["role"] = role
        return redirect(url_for("room", role=role))

    return render_template("home.html")

@app.route("/room", methods=["POST", "GET"])
def room(role):
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    if role == "Therapist":
      return render_template("room_therapist.html", code=room, messages=rooms[room]["messages"])
