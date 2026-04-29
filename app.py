from flask import Flask, request, jsonify
import uuid
import time
import random

app = Flask(__name__)

# In-memory session store (simulates Firestore for prototype phase)
sessions = {}

# ── Health check ──────────────────────────────────────────────────────────────

@app.route("/ping", methods=["GET"])
def ping():
    """Latency probe used by load testing and Cloud Monitoring."""
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "server": "game-server-pod"
    }), 200

# ── Session management ────────────────────────────────────────────────────────

@app.route("/session/create", methods=["POST"])
def create_session():
    """
    Creates a new player session.
    Body (JSON): { "player_id": "string", "display_name": "string" }
    Returns: session_id, assigned server pod, initial player state
    """
    data = request.get_json(silent=True) or {}
    player_id = data.get("player_id", str(uuid.uuid4()))
    display_name = data.get("display_name", f"Player_{random.randint(1000,9999)}")

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "session_id": session_id,
        "player_id": player_id,
        "display_name": display_name,
        "created_at": time.time(),
        "last_updated": time.time(),
        "status": "active",
        "state": {
            "position_x": 0.0,
            "position_y": 0.0,
            "health": 100,
            "score": 0
        }
    }

    return jsonify({
        "session_id": session_id,
        "player_id": player_id,
        "display_name": display_name,
        "server_pod": "game-server-pod",
        "status": "active",
        "message": "Session created successfully"
    }), 201


@app.route("/session/state/<session_id>", methods=["GET"])
def get_state(session_id):
    """Returns current player state for the given session."""
    session = sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "session_id": session_id,
        "player_id": session["player_id"],
        "display_name": session["display_name"],
        "status": session["status"],
        "state": session["state"],
        "last_updated": session["last_updated"]
    }), 200


@app.route("/session/update", methods=["POST"])
def update_state():
    """
    Updates player game state.
    Body (JSON): { "session_id": "string", "state": { "position_x": float, ... } }
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    new_state = data.get("state", {})

    if not session_id or session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    sessions[session_id]["state"].update(new_state)
    sessions[session_id]["last_updated"] = time.time()

    return jsonify({
        "session_id": session_id,
        "state": sessions[session_id]["state"],
        "last_updated": sessions[session_id]["last_updated"],
        "message": "State updated"
    }), 200


@app.route("/session/end/<session_id>", methods=["DELETE"])
def end_session(session_id):
    """Terminates a player session and cleans up state."""
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    sessions[session_id]["status"] = "ended"
    sessions.pop(session_id)

    return jsonify({
        "session_id": session_id,
        "message": "Session ended and cleaned up"
    }), 200


# ── Server info (bonus endpoint for demo) ────────────────────────────────────

@app.route("/status", methods=["GET"])
def server_status():
    """Returns active session count and server metadata. Useful for demo."""
    active = sum(1 for s in sessions.values() if s["status"] == "active")
    return jsonify({
        "active_sessions": active,
        "total_sessions_tracked": len(sessions),
        "server_pod": "game-server-pod",
        "uptime": time.time()
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
