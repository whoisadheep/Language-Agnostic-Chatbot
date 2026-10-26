"""
GridCRM Cloud Synchronization Engine
Syncs voice & chat call data directly to GridCRM Firebase Firestore database.
Collections synced:
  - customers: { ownerId, name, phone, address, created_at }
  - calls:     { ownerId, customer_id, customer: {name, phone}, call_type, problem_description,
                 priority, status, technician_assigned, raw_input, source, created_at, updated_at }
  - call_updates: { ownerId, call_id, note, status_change, created_at }
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any, List
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv(override=True)

_firebase_initialized = False

def init_firebase() -> bool:
    """Initialize Firebase Admin SDK using GridCRM service account credentials."""
    global _firebase_initialized
    if _firebase_initialized or (firebase_admin._apps and len(firebase_admin._apps) > 0):
        _firebase_initialized = True
        return True

    # Check file path
    json_path = os.getenv("GRIDCRM_FIREBASE_JSON_PATH", "/home/whoisadheep/Documents/GridCRM/backend/firebase-admin.json")
    if os.path.exists(json_path):
        try:
            cred = credentials.Certificate(json_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print(f"[GridCRM] Firebase initialized from {json_path}")
            return True
        except Exception as e:
            print(f"[GridCRM] Error initializing Firebase from file: {e}")

    # Check direct JSON string
    json_str = os.getenv("GRIDCRM_FIREBASE_JSON")
    if json_str:
        try:
            cred_dict = json.loads(json_str)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("[GridCRM] Firebase initialized from GRIDCRM_FIREBASE_JSON")
            return True
        except Exception as e:
            print(f"[GridCRM] Error initializing Firebase from JSON: {e}")

    print("[GridCRM] Warning: Service account credentials not found")
    return False


EXTRACTION_PROMPT = """You are an autonomous CRM data extraction engine.
Given the conversation transcript between an AI agent and a customer, extract the caller's details into valid JSON.

Return ONLY a clean JSON object with these exact keys:
{
  "customer_name": string or null (the caller's full name if stated, else "Valued Customer"),
  "caller_phone": string or null (the phone number if mentioned),
  "call_type": one of ["Service", "Installation", "AMC", "Sales", "Other"],
  "problem_description": string (clear summary of customer issue or request),
  "priority": one of ["Low", "Medium", "High"]
}

Guidelines:
- Infer call_type accurately:
    - "Service": repairing, fixing, issue, bug, maintenance, not working.
    - "Installation": new setup, deployment, purchasing equipment.
    - "AMC": annual contracts.
    - "Sales": pricing, demo, quotation, general inquiries.
- Infer priority from urgency cues ("urgent", "down", "broken", "critical" -> High, else Medium).
- Keep problem_description concise and actionable."""


async def extract_call_crm_data(conversation_history: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Uses Groq to extract structured CRM fields from conversation turns."""
    if not conversation_history:
        return None

    transcript_lines = []
    for msg in conversation_history:
        role = "Customer" if msg.get("role") == "user" else "Agent"
        transcript_lines.append(f"{role}: {msg.get('content', '')}")
    transcript = "\n".join(transcript_lines)

    try:
        from router import ai_router
        res = await ai_router.complete_async(
            prompt=transcript,
            system_prompt=EXTRACTION_PROMPT,
            max_tokens=300
        )
        raw = res.get("text", "").strip()

        # Clean markdown wrappers
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)
        return data
    except Exception as e:
        print(f"[GridCRM] Extraction error: {e}")
        return None


def _write_to_firestore_sync(
    owner_id: str,
    customer_name: str,
    phone: Optional[str],
    call_type: str,
    problem_description: str,
    priority: str,
    raw_input: str,
    source: str = "OmniAgent Voice"
) -> Dict[str, Any]:
    """Synchronous Firestore transaction write."""
    db = firestore.client()

    # 1. Customer Resolution
    customer_id = None
    customer_data = {"name": customer_name, "phone": phone or ""}

    if phone:
        existing = db.collection("customers").where("ownerId", "==", owner_id).where("phone", "==", phone).get()
        if existing:
            customer_doc = existing[0]
            customer_id = customer_doc.id
            customer_data = customer_doc.to_dict()
            if customer_name and customer_name != "Valued Customer":
                customer_doc.reference.update({"name": customer_name})
                customer_data["name"] = customer_name

    if not customer_id:
        _, new_ref = db.collection("customers").add({
            "ownerId": owner_id,
            "name": customer_name,
            "phone": phone or "",
            "address": "",
            "created_at": firestore.SERVER_TIMESTAMP,
        })
        customer_id = new_ref.id

    # 2. Call Ticket Creation
    call_ref = db.collection("calls").document()
    call_data = {
        "ownerId": owner_id,
        "customer_id": customer_id,
        "customer": {
            "name": customer_data.get("name", customer_name),
            "phone": customer_data.get("phone", phone or ""),
        },
        "call_type": call_type,
        "problem_description": problem_description,
        "priority": priority,
        "status": "Pending",
        "technician_assigned": None,
        "raw_input": raw_input,
        "source": source,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    call_ref.set(call_data)

    # 3. Audit Log Update
    db.collection("call_updates").add({
        "ownerId": owner_id,
        "call_id": call_ref.id,
        "note": f"OmniAgent: Ticket auto-logged from {source}.",
        "status_change": "Pending",
        "created_at": firestore.SERVER_TIMESTAMP,
    })

    print(f"[GridCRM] Successfully synced ticket {call_ref.id} for {customer_name}")
    return {
        "call_id": call_ref.id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "phone": phone,
        "call_type": call_type,
        "priority": priority,
        "problem_description": problem_description
    }


async def push_to_gridcrm(
    conversation_history: List[Dict[str, str]],
    caller_phone: Optional[str] = None,
    source: str = "OmniAgent Voice"
) -> Optional[Dict[str, Any]]:
    """Asynchronously extracts and synchronizes conversation to GridCRM Cloud Firestore."""
    owner_id = os.getenv("GRIDCRM_OWNER_ID", "Rudra")
    if not init_firebase():
        return None

    extracted = await extract_call_crm_data(conversation_history)
    if not extracted:
        # Fallback to basic transcript summary
        extracted = {
            "customer_name": "Valued Caller",
            "caller_phone": caller_phone or "Web Audio",
            "call_type": "Service",
            "problem_description": "General Customer Voice Inquiry",
            "priority": "Medium"
        }

    customer_name = extracted.get("customer_name") or "Valued Caller"
    phone = extracted.get("caller_phone") or caller_phone
    call_type = extracted.get("call_type", "Service")
    problem = extracted.get("problem_description", "Voice Consultation Request")
    priority = extracted.get("priority", "Medium")

    transcript_lines = [f"{m.get('role', 'caller').capitalize()}: {m.get('content', '')}" for m in conversation_history]
    raw_input = "\n".join(transcript_lines)

    result = await asyncio.to_thread(
        _write_to_firestore_sync,
        owner_id, customer_name, phone, call_type, problem, priority, raw_input, source
    )
    return result


def fetch_recent_gridcrm_tickets(limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch live tickets from GridCRM Firestore for real-time dashboard telemetry."""
    if not init_firebase():
        return []

    try:
        db = firestore.client()
        owner_id = os.getenv("GRIDCRM_OWNER_ID", "Rudra")
        docs = db.collection("calls").where("ownerId", "==", owner_id).limit(limit).get()
        
        tickets = []
        for doc in docs:
            d = doc.to_dict()
            # Convert timestamp to ISO string
            created_at = d.get("created_at")
            time_str = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)

            tickets.append({
                "id": doc.id,
                "customer_name": d.get("customer", {}).get("name", "Unknown"),
                "phone": d.get("customer", {}).get("phone", ""),
                "call_type": d.get("call_type", "General"),
                "problem_description": d.get("problem_description", ""),
                "priority": d.get("priority", "Medium"),
                "status": d.get("status", "Pending"),
                "source": d.get("source", "GridCRM"),
                "created_at": time_str
            })
        return tickets
    except Exception as e:
        print(f"[GridCRM] Error fetching tickets: {e}")
        return []
