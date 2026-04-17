# English Teaching Application (AI Tutor)

Full-stack app for learning English with an AI tutor: a **React** frontend talks to a **Flask** backend that combines NLP (spaCy, NLTK, LanguageTool), pronunciation helpers, and **Groq** for conversational AI.

## Repository layout

| Path | Role |
|------|------|
| `backend/` | Flask API (`complete_english_tutor.py`), JWT auth, sessions, tutoring logic |
| `frontend/` | Create React App UI (`ai-english-tutor-frontend`), proxies API to port 5000 |

## Prerequisites

- **Python** 3.10+ recommended (3.8+ per backend notes)
- **Node.js** 18+ and npm (for the frontend)
- **Groq API key** for AI chat responses ([Groq Console](https://console.groq.com/))

## Backend setup

From the `backend` folder:

1. Create a virtual environment and install dependencies:

   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Download the spaCy English model:

   ```bash
   python -m spacy download en_core_web_sm
   ```

3. Configure environment variables. Copy `.env.example` to `.env` and set at least:

   - `GROQ_API_KEY` — required for AI tutor replies (see tip printed when the server starts).
   - `JWT_SECRET_KEY` — change from the default before any real deployment.

4. Start the API (default **http://127.0.0.1:5000**):

   ```bash
   python complete_english_tutor.py
   ```

On first run, NLTK data is downloaded automatically when possible.

## Frontend setup

From the `frontend` folder:

```bash
cd frontend
npm install
npm start
```

The dev server runs on **http://localhost:3000** and uses the `proxy` in `package.json` to forward API calls to `http://localhost:5000`.

## Production build (frontend)

```bash
cd frontend
npm run build
```

Serve the `build/` folder with your static host or reverse proxy; point the app’s API base URL to your deployed backend as needed.

## Configuration notes

- CORS is enabled for `http://localhost:3000` and `http://localhost:5173` in the backend.
- Root `requirements.txt` is a broad dependency list; day-to-day backend work should use **`backend/requirements.txt`**.
