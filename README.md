# 🌐 OmniLingua — Language Agnostic AI Chatbot

A production-grade, language-agnostic chatbot that auto-detects the user's language, translates it to English for AI processing via Google Gemini, and translates the response back — all in real-time. Built with **FastAPI**, **React**, and a premium **Tailwind CSS** UI.

---

## ✨ Features

- **Auto Language Detection** — Detects 50+ languages using `langdetect`
- **Real-Time Translation** — Seamless translation via LibreTranslate API
- **AI-Powered Responses** — Google Gemini 2.5 Flash for intelligent replies
- **Admin Analytics Dashboard** — Pie charts, bar charts, live feed, and KPI cards
- **Persistent Chat History** — Conversations survive browser refreshes via `localStorage`
- **Rate Limiting** — 20 requests/minute per IP via `slowapi`
- **Robust Error Handling** — Graceful fallbacks for API failures with toast notifications
- **SQLite Analytics** — Every message is logged with language, response time, and timestamp

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                      │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │   ChatView   │    │ AdminDashboard   │    │  Toast System     │  │
│  │  (/ route)   │    │  (/admin route)  │    │  (Error/Warning)  │  │
│  └──────┬───────┘    └────────┬─────────┘    └───────────────────┘  │
│         │                     │                                     │
│         │   POST /chat        │   GET /analytics                    │
└─────────┼─────────────────────┼─────────────────────────────────────┘
          │                     │
          ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI + Uvicorn)                     │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │  /chat      │  │  /analytics  │  │  /health    │  │ /welcome │ │
│  │  (POST)     │  │  (GET)       │  │  (GET)      │  │ (GET)    │ │
│  └──────┬──────┘  └──────┬───────┘  └─────────────┘  └──────────┘ │
│         │                │                                          │
│         ▼                ▼                                          │
│  ┌─────────────────────────────┐                                   │
│  │   SQLite (analytics.db)     │                                   │
│  │   via SQLAlchemy ORM        │                                   │
│  └─────────────────────────────┘                                   │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │               Translation Pipeline                       │      │
│  │                                                          │      │
│  │  1. langdetect  ──▶  Detect Language                     │      │
│  │  2. LibreTranslate ──▶  Translate to English             │      │
│  │  3. Google Gemini ──▶  Generate AI Response              │      │
│  │  4. LibreTranslate ──▶  Translate back to User Lang      │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
Language Agnostic AI Chatbot/
├── backend/
│   ├── main.py              # FastAPI app, routes, translation pipeline
│   ├── database.py          # SQLAlchemy models & DB setup
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # Environment variables (GEMINI_API_KEY)
│   ├── analytics.db         # SQLite database (auto-created)
│   └── tests/
│       ├── test_language_detection.py
│       ├── test_translation.py
│       └── test_api.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Router setup
│   │   ├── index.css        # Tailwind + design tokens
│   │   └── components/
│   │       ├── ChatView.jsx         # Main chat interface
│   │       └── AdminDashboard.jsx   # Analytics dashboard
│   ├── package.json
│   └── index.html
└── README.md
```

---

## 🚀 Setup Instructions

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Google Gemini API Key** — [Get one here](https://aistudio.google.com/apikey)

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/language-agnostic-ai-chatbot.git
cd language-agnostic-ai-chatbot
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

---

## 🔐 Environment Variables

Create a `.env` file inside the `backend/` directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

| Variable         | Required | Description                          |
|------------------|----------|--------------------------------------|
| `GEMINI_API_KEY` | ✅ Yes   | Google Gemini API key for AI responses |

---

## ▶️ How to Run Locally

### Start the Backend

```bash
cd backend
.\venv\Scripts\uvicorn main:app --reload
```

The API server starts at `http://localhost:8000`.

### Start the Frontend

```bash
cd frontend
npm run dev
```

The React app starts at `http://localhost:5173`.

### Access the App

| Page               | URL                         |
|--------------------|-----------------------------|
| Chat Interface     | http://localhost:5173/       |
| Admin Dashboard    | http://localhost:5173/admin  |
| Health Check       | http://localhost:8000/health |
| Analytics API      | http://localhost:8000/analytics |

---

## 📡 API Reference

### `POST /chat`

Send a message and receive an AI-generated response in the user's language.

**Request:**
```json
{
  "message": "Bonjour, comment allez-vous?",
  "override_language": null
}
```

**Response (200):**
```json
{
  "response": "Bonjour! Je vais très bien, merci de demander. Comment puis-je vous aider aujourd'hui?",
  "detected_language": "fr",
  "warning": null
}
```

**Response (429 — Rate Limited):**
```json
{
  "error": "Rate limit exceeded: 20 per 1 minute"
}
```

### `GET /health`

Check system status.

**Response (200):**
```json
{
  "status": "ok",
  "gemini": "configured"
}
```

### `GET /analytics`

Retrieve aggregated analytics data.

**Response (200):**
```json
{
  "total_messages": 42,
  "languages_detected": [
    { "name": "en", "value": 20 },
    { "name": "fr", "value": 12 },
    { "name": "hi", "value": 10 }
  ],
  "avg_response_times": [
    { "language": "en", "avg_ms": 1250.5 },
    { "language": "fr", "avg_ms": 3400.2 }
  ],
  "messages_per_hour": [
    { "hour": "2026-04-26 14:00", "count": 15 }
  ],
  "recent_messages": [
    {
      "id": 1,
      "message": "Hello",
      "language": "en",
      "time": "2026-04-26T14:30:00"
    }
  ]
}
```

### `GET /welcome?lang=hi`

Get a localized welcome message.

**Response (200):**
```json
{
  "message": "ओमनीलिंगुआ में आपका स्वागत है! किसी भी भाषा में संदेश टाइप करें..."
}
```

---

## 🧪 Running Tests

```bash
cd backend

# Run all unit tests (language detection + API endpoints)
.\venv\Scripts\pytest tests/ -v

# Run only language detection tests
.\venv\Scripts\pytest tests/test_language_detection.py -v

# Run only API endpoint tests
.\venv\Scripts\pytest tests/test_api.py -v

# Run integration tests (requires internet for LibreTranslate)
.\venv\Scripts\pytest tests/test_translation.py -v -m integration
```

---

## 🛡️ Error Handling

| Scenario                    | Backend Behavior                     | Frontend Behavior             |
|-----------------------------|--------------------------------------|-------------------------------|
| Language detection fails    | Defaults to English, sends `warning` | Shows amber warning toast     |
| Translation API down        | Skips translation, responds in English | Shows warning toast           |
| Rate limit exceeded (20/min)| Returns `429`                        | Shows red error toast         |
| Message > 500 characters    | Returns `422`                        | Input disabled + red counter  |
| Gemini API key missing      | Returns `500`                        | Shows error message in chat   |

---

## 📊 Tech Stack

| Layer     | Technology                              |
|-----------|-----------------------------------------|
| Frontend  | React 19, Vite 8, Tailwind CSS 3        |
| Backend   | FastAPI, Uvicorn, SQLAlchemy, slowapi    |
| AI        | Google Gemini 2.5 Flash (`google-genai`) |
| Translation | LibreTranslate (Public API)           |
| Detection | langdetect                              |
| Database  | SQLite                                  |
| Charts    | Recharts                                |

---

## 📄 License

MIT License — feel free to use, modify, and distribute.
