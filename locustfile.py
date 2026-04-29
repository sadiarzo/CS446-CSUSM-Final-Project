from locust import HttpUser, task, between
import random
import uuid


class MultiplayerGameUser(HttpUser):
    """
    Simulates a multiplayer game player.
    Each user creates a session, sends periodic state updates and pings,
    then occasionally ends the session — modelling realistic gameplay traffic.
    """

    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Create a session when the simulated player joins."""
        self.player_id = f"player_{uuid.uuid4().hex[:8]}"
        self.session_id = None

        response = self.client.post(
            "/session/create",
            json={
                "player_id": self.player_id,
                "display_name": f"LoadTest_{random.randint(1000, 9999)}"
            },
            name="POST /session/create"
        )
        if response.status_code == 201:
            self.session_id = response.json().get("session_id")

    @task(10)
    def send_ping(self):
        """High-frequency latency probe — represents heartbeat traffic."""
        self.client.get("/ping", name="GET /ping")

    @task(5)
    def update_state(self):
        """Send a player position/score update — represents gameplay events."""
        if not self.session_id:
            return
        self.client.post(
            "/session/update",
            json={
                "session_id": self.session_id,
                "state": {
                    "position_x": round(random.uniform(0, 1000), 2),
                    "position_y": round(random.uniform(0, 1000), 2),
                    "score": random.randint(0, 5000),
                    "health": random.randint(50, 100)
                }
            },
            name="POST /session/update"
        )

    @task(3)
    def get_state(self):
        """Read current player state — represents client-side syncs."""
        if not self.session_id:
            return
        self.client.get(
            f"/session/state/{self.session_id}",
            name="GET /session/state/[id]"
        )

    @task(1)
    def server_status(self):
        """Occasionally check server status."""
        self.client.get("/status", name="GET /status")

    def on_stop(self):
        """End session when the simulated player disconnects."""
        if self.session_id:
            self.client.delete(
                f"/session/end/{self.session_id}",
                name="DELETE /session/end/[id]"
            )
