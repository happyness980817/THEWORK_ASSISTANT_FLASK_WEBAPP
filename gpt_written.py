from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import join_room, leave_room, send, SocketIO, emit
import random
from string import ascii_uppercase
from dotenv import load_dotenv
import os
from openai import OpenAI

app = Flask(__name__)
app.config["SECRET_KEY"] = "secretkeyname"
socketio = SocketIO(app)

rooms = {}

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
ASSISTANT_ID = os.getenv('ASSISTANT_ID')

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
        return redirect(url_for("room"))

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

@app.route("/create_thread", methods=["POST"])
def create_thread():
    empty_thread = client.beta.threads.create()
    return jsonify({"thread_id": empty_thread.id})

@app.route("/add_message_to_thread", methods=["POST"])
def add_message_to_thread():
    data = request.get_json()
    thread_id = data["thread_id"]
    message = data["message"]
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message
    )
    return jsonify({"status": "message added"})

@app.route("/run_assistant", methods=["POST"])
def run_assistant():
    data = request.get_json()
    thread_id = data["thread_id"]
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID
    )
    response_message = run['messages'][-1]['content']
    return jsonify({"message": response_message})

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    content = {
        "name": session.get("name"),
        "message": data["data"],
        "role": data["role"]
    }

    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['data']}")

    if content["role"] == "Therapist":
        response = process_assistant_message(data["data"], data["thread_id"])
        ai_content = {
            "name": "AI Assistant",
            "message": response,
            "role": "Assistant"
        }
        emit("assistant_message", ai_content, to=room)
        rooms[room]["messages"].append(ai_content)
        print(f"AI Assistant recommended: {response}")

def process_assistant_message(user_message, thread_id):
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID
    )

    response_message = run['messages'][-1]['content']
    return response_message

@socketio.on("connect")
def connect():
    room = session.get("room")
    name = session.get("name")
    role = session.get("role")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has entered the room", "role": role}, to=room)
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
            del rooms[room]

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True)
