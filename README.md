# Scalable Cloud Architecture for Multiplayer Games

## Overview

A cloud-native multiplayer game server backend deployed on Google Kubernetes Engine (GKE) with horizontal pod autoscaling, distributed load balancing, and Cloud Monitoring integration. The system simulates real-time multiplayer session management and serves as a testbed for evaluating cloud-native scalability against centralized server deployments.

## Architecture

- **Compute:** Google Kubernetes Engine (GKE) — `game-server-cluster` in `us-central1-a`
- **Container Registry:** Google Container Registry (GCR)
- **Networking:** Cloud Load Balancing (LoadBalancer service)
- **Autoscaling:** Horizontal Pod Autoscaler — CPU-based, 2–5 replicas
- **Storage (planned):** Cloud Firestore for distributed session persistence
- **Messaging (planned):** Cloud Pub/Sub for inter-pod event sync
- **Monitoring:** Cloud Monitoring for latency, throughput, and pod scaling metrics

## Repository Structure

```
.
├── app.py                # Flask REST API — session management endpoints
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container image definition
├── deployment.yaml       # Kubernetes Deployment + Service + HPA
├── cloudbuild.yaml       # Cloud Build automation config
├── locustfile.py         # Load testing scenarios (Locust)
└── README.md
```

## API Endpoints

| Method | Endpoint                       | Description                                 |
|--------|--------------------------------|---------------------------------------------|
| GET    | `/ping`                        | Health check / latency probe                |
| POST   | `/session/create`              | Create a new player session                 |
| GET    | `/session/state/{session_id}`  | Retrieve current player state               |
| POST   | `/session/update`              | Update player state (position, score, etc.) |
| DELETE | `/session/end/{session_id}`    | Terminate session and clean up state        |
| GET    | `/status`                      | Server status and active session count      |

## Local Development

```bash
pip install -r requirements.txt
python app.py
# Server runs on http://localhost:8080
```

## Build & Deploy

```bash
# 1. Build and push container image
gcloud builds submit --tag gcr.io/$PROJECT_ID/game-server:v1

# 2. Deploy to GKE
kubectl apply -f deployment.yaml

# 3. Verify deployment
kubectl get pods
kubectl get svc game-server-service
kubectl get hpa game-server-hpa
```

## Load Testing

```bash
pip install locust
locust -f locustfile.py --host http://<EXTERNAL-IP>
# Open http://localhost:8089 to configure and run the test
```

## Performance Goals

Per the project hypothesis: a 20%+ reduction in average player latency under high concurrent load (100+ simulated users) compared to a baseline single-instance deployment, with stable throughput maintained via HPA-driven scaling.
