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

assistant = client.beta.assistants.retrieve(ASSISTANT_ID)
# print(assistant)

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
def room():
    room = session.get("room")
    role = session.get("role")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    if role == "Therapist":
        return render_template("room_therapist.html", code=room, messages=rooms[room]["messages"])
    else:
        return render_template("room_client.html", code=room, messages=rooms[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    role = session.get("role")
    if room not in rooms:
        return

    content = {
        "name": session.get("name"),
        "message": data["data"],
        "role": data["role"]
    }



    if role == "Client":
        # 1) create thread (assistant function)
        room = session.get("room")
        thread_id = client.beta.threads.create()
        thread_room = client.beta.threads.retrieve(thread_id)
        # 2) message -> assistant input 으로 전달
        
        # 3) assistant.run()
        # 4) output -> "assistant tips" 로 "therapist.html" 에 전달
        send(content, to=room)
        rooms[room]["messages"].append(content)
        print(f"{session.get('name')} said: {data['data']}")
    else:
        send(content, to=room)
        rooms[room]["messages"].append(content)
        print(f"{session.get('name')} said: {data['data']}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    role = session.get("role")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has entered the room", "role": role}, to=room)  # sends messages to everyone in the room
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]  # delete room when every user leaves

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True)  # for development, automatically refreshes
    # socketio.run(app, host='0.0.0.0') # for deployment
