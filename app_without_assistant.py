from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO, emit
import random
from string import ascii_uppercase

app = Flask(__name__)
app.config["SECRET_KEY"] = "secretkeyname"
socketio = SocketIO(app)

rooms = {}

def generate_unique_code(length):
    while True:
        code = "".join(random.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            break
    return code  # generates new codes (not in rooms) with length of "length" parameter.

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")  # 
        code = request.form.get("code")
        join = request.form.get("join", False)
        # if "join" doesn't exist in the dictionary, it returns 'False' instead of 'None'.
        create = request.form.get("create", False)  # join and create don't have a value(key).
        role = request.form.get("role")

        if not name:  # this means the user didn't give a name or empty.
            return render_template("home.html", error="Please enter a name.", code=code, name=name, role=role)

        if join != False and not code:  # when user attempts to join but doesn't enter a code
            return render_template("home.html", error="Please enter a room code.", code=code, name=name, role=role)

        if not role:
            return render_template("home.html", error="Please select a role.", code=code, name=name, role=role)

        room = code
        if create != False:
            room = generate_unique_code(8)
            rooms[room] = {"members": 0, "messages": []}  # initializes rooms dictionary
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name  # session is a semi-permanent way to store information about a user
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
