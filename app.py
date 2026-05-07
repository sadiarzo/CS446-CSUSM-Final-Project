"""
Multiplayer Game Server — v3 with Cloud Firestore + Cloud Pub/Sub.

Adds event publishing on session lifecycle changes for downstream
analytics and inter-service communication. Events are best-effort —
publish failures are logged but never block the API response, since
the source of truth is Firestore.
"""
from flask import Flask, request, jsonify
from google.cloud import firestore
from google.cloud import pubsub_v1
import uuid
import time
import random
import os
import socket
import logging
import json

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)

# ── Cloud clients ────────────────────────────────────────────────────────────
db = firestore.Client()
SESSIONS = db.collection("sessions")
PLAYERS = db.collection("players")

publisher = pubsub_v1.PublisherClient()
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "multiplayer-cloud-490706")
TOPIC_PATH = publisher.topic_path(PROJECT_ID, "session-events")

POD_NAME = os.environ.get("POD_NAME", socket.gethostname())


def publish_event(event_type, session_id, payload=None):
    """Publish a session event to Pub/Sub. Best-effort — never raises."""
    try:
        message = {
            "event_type": event_type,
            "session_id": session_id,
            "timestamp": time.time(),
            "pod": POD_NAME,
            "payload": payload or {},
        }
        publisher.publish(
            TOPIC_PATH,
            data=json.dumps(message).encode("utf-8"),
            event_type=event_type,
        )
        log.info(f"Published {event_type} for session {session_id}")
    except Exception as e:
        log.warning(f"Pub/Sub publish failed (non-fatal): {e}")


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "Multiplayer Game Server",
        "version": "v3",
        "storage": "Cloud Firestore",
        "messaging": "Cloud Pub/Sub",
        "pod": POD_NAME,
    }), 200


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "pod": POD_NAME,
        "version": "v3"
    }), 200


@app.route("/status", methods=["GET"])
def server_status():
    try:
        active_query = SESSIONS.where("status", "==", "active").limit(100).stream()
        active_count = sum(1 for _ in active_query)
    except Exception as e:
        log.warning(f"Status query failed: {e}")
        active_count = -1
    return jsonify({
        "active_sessions": active_count,
        "pod": POD_NAME,
        "storage": "firestore",
        "messaging": "pubsub",
        "uptime": time.time(),
    }), 200


@app.route("/session/create", methods=["POST"])
def create_session():
    data = request.get_json(silent=True) or {}
    player_id = data.get("player_id", str(uuid.uuid4()))
    display_name = data.get("display_name", f"Player_{random.randint(1000, 9999)}")
    session_id = str(uuid.uuid4())
    now = time.time()

    session_doc = {
        "session_id": session_id,
        "player_id": player_id,
        "display_name": display_name,
        "created_at": now,
        "last_updated": now,
        "status": "active",
        "server_pod": POD_NAME,
        "state": {
            "position_x": 0.0,
            "position_y": 0.0,
            "health": 100,
            "score": 0,
        }
    }

    try:
        SESSIONS.document(session_id).set(session_doc)
        PLAYERS.document(player_id).set(
            {"display_name": display_name, "last_session_at": now},
            merge=True
        )
    except Exception as e:
        log.error(f"Firestore write failed: {e}")
        return jsonify({"error": "storage unavailable"}), 503

    publish_event("session.created", session_id, {
        "player_id": player_id,
        "display_name": display_name,
    })

    return jsonify({
        "session_id": session_id,
        "player_id": player_id,
        "display_name": display_name,
        "server_pod": POD_NAME,
        "status": "active",
        "message": "Session created"
    }), 201


@app.route("/session/state/<session_id>", methods=["GET"])
def get_state(session_id):
    try:
        doc = SESSIONS.document(session_id).get()
    except Exception as e:
        log.error(f"Firestore read failed: {e}")
        return jsonify({"error": "storage unavailable"}), 503

    if not doc.exists:
        return jsonify({"error": "Session not found"}), 404

    s = doc.to_dict()
    return jsonify({
        "session_id": session_id,
        "player_id": s["player_id"],
        "display_name": s["display_name"],
        "status": s["status"],
        "state": s["state"],
        "server_pod_origin": s.get("server_pod"),
        "served_by_pod": POD_NAME,
        "last_updated": s["last_updated"],
    }), 200


@app.route("/session/update", methods=["POST"])
def update_state():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    new_state = data.get("state", {})

    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    ref = SESSIONS.document(session_id)
    try:
        doc = ref.get()
        if not doc.exists:
            return jsonify({"error": "Session not found"}), 404
        update_payload = {f"state.{k}": v for k, v in new_state.items()}
        update_payload["last_updated"] = time.time()
        ref.update(update_payload)
    except Exception as e:
        log.error(f"Firestore update failed: {e}")
        return jsonify({"error": "storage unavailable"}), 503

    if "score" in new_state:
        publish_event("session.updated", session_id, {"score": new_state["score"]})

    return jsonify({
        "session_id": session_id,
        "served_by_pod": POD_NAME,
        "message": "State updated"
    }), 200


@app.route("/session/end/<session_id>", methods=["DELETE"])
def end_session(session_id):
    ref = SESSIONS.document(session_id)
    try:
        doc = ref.get()
        if not doc.exists:
            return jsonify({"error": "Session not found"}), 404
        ref.update({"status": "ended", "ended_at": time.time()})
    except Exception as e:
        log.error(f"Firestore delete failed: {e}")
        return jsonify({"error": "storage unavailable"}), 503

    publish_event("session.ended", session_id)

    return jsonify({
        "session_id": session_id,
        "served_by_pod": POD_NAME,
        "message": "Session ended"
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
