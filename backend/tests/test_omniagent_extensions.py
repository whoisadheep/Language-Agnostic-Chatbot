from fastapi.testclient import TestClient
from main import app
from database import Base, engine

client = TestClient(app)

def test_telemetry_endpoint():
    response = client.get("/api/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)
    assert len(data["providers"]) >= 3
    for p in data["providers"]:
        assert "name" in p
        assert "state" in p
        assert p["state"] in ["CLOSED", "OPEN", "HALF_OPEN"]

def test_solve_form_trick_question():
    req_payload = {
        "profile": {
            "full_name": "Alex Mercer",
            "skills": ["Python", "FastAPI", "React", "Docker"],
            "degree": "Bachelor of Technology in Computer Science",
            "university": "Apex University",
            "gpa": "3.9"
        },
        "fields": [
            {
                "id": "q1",
                "question": "Which of the following programming languages is NOT known by the applicant?",
                "type": "text"
            },
            {
                "id": "q2",
                "question": "What degree did the candidate obtain?",
                "type": "text"
            }
        ]
    }
    response = client.post("/api/solve-form", json=req_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    solved = data["solved_fields"]
    # Check that trick question (NOT) was flagged
    assert solved[0]["review_recommended"] is True
    assert "Trick" in solved[0]["reason"] or "Negative" in solved[0]["reason"]

def test_memories_crud():
    # 1. Create a memory snippet
    create_payload = {
        "category": "project",
        "title": "Voicera Voice Agent",
        "content": "Engineered real-time bidirectional audio streaming with WebSockets and VAD"
    }
    create_res = client.post("/api/memories", json=create_payload)
    assert create_res.status_code == 200
    snip_id = create_res.json()["id"]

    # 2. Get memories
    get_res = client.get("/api/memories")
    assert get_res.status_code == 200
    memories = get_res.json()
    assert any(m["id"] == snip_id for m in memories)

    # 3. Delete memory
    del_res = client.delete(f"/api/memories/{snip_id}")
    assert del_res.status_code == 200

def test_voice_websocket_and_phone():
    # 1. Test /phone endpoint returns HTML
    phone_res = client.get("/phone")
    assert phone_res.status_code == 200
    assert "html" in phone_res.headers.get("content-type", "").lower()

    # 2. Test websocket connection and initial greeting dispatch
    with client.websocket_connect("/ws/voice") as ws:
        init_msg = ws.receive_json()
        assert init_msg.get("event") == "connected"
        
        ws.send_json({"event": "start"})
        transcript_msg = ws.receive_json()
        assert transcript_msg.get("event") == "transcript"
        assert transcript_msg.get("role") == "assistant"
        
        # Audio media chunk should follow
        media_msg = ws.receive_json()
        assert media_msg.get("event") == "media"
        assert "payload" in media_msg.get("media", {})
