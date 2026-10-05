# Smart Study Generator 🎓
### AI-Powered Personalized Study Companion

> **Model**: Groq · `qwen/qwen3-27b`  
> **Stack**: Python · Flask · HTML/CSS/JS

---

## What It Does

Smart Study Generator is an **agentic AI application** that acts as your personal study companion. Give it your study material (PDFs, images, notes) and student profile, and it will:

- 📋 **Summarise** long chapters into concise bullet-point notes
- 🎯 **Identify** top exam topics and weak areas with Focus Alerts
- 🃏 **Generate Flashcards** for active recall practice
- 📝 **Create Practice Quizzes** (MCQ with explanations)
- 🗺️ **Build Concept Maps** showing topic relationships
- 📅 **Design Study Plans** tailored to your exam date and hours
- 📊 **Track Progress** via a real-time dashboard

---

## Project Structure

```
smart-study-agent/
├── frontend/
│   ├── index.html           ← Main UI
│   ├── style.css            ← Responsive styling
│   └── script.js            ← Frontend logic (no API key here)
├── backend/
│   ├── app.py               ← Flask API server
│   ├── agent.py             ← Agentic pipeline
│   ├── groq_client.py       ← Groq API client
│   ├── guardrails.py        ← Security & sanitisation
│   └── document_processor.py ← PDF/image/text extraction
├── .env.example             ← Config template
├── requirements.txt
├── smart_study_agent_plan.md ← Full SDLC documentation
├── README.md                ← This file
└── run_smart_study.bat      ← One-click Windows launcher
```

---

## Quick Start (Windows)

### Step 1 — Get a Groq API Key
1. Go to [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign in (free) and create a new API key
3. Copy the key

### Step 2 — Configure Environment
```bat
cd smart-study-agent
copy .env.example .env
```
Open `.env` in Notepad and replace `your_groq_api_key_here` with your actual key:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 3 — Launch the Application
Double-click `run_smart_study.bat` or run it from a terminal:
```bat
run_smart_study.bat
```

The script will:
1. Create a Python virtual environment (`venv/`)
2. Install all dependencies from `requirements.txt`
3. Verify that `.env` exists
4. Start the Flask backend on `http://127.0.0.1:5000`

### Step 4 — Open the Frontend
Open `frontend/index.html` directly in your browser, **or** use a local HTTP server (recommended):
```bash
# Option A — Python built-in server (from smart-study-agent/frontend/)
python -m http.server 5500

# Option B — VS Code Live Server extension
# Right-click index.html → Open with Live Server
```
Then browse to `http://127.0.0.1:5500`.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | [python.org](https://python.org) |
| pip | Latest | Included with Python |
| Groq API Key | — | Free at [console.groq.com](https://console.groq.com) |
| Tesseract OCR | 5.x (optional) | Required for image OCR. [UB Mannheim builds for Windows](https://github.com/UB-Mannheim/tesseract/wiki) |

> **Note**: PDF text extraction and all text-based features work without Tesseract. OCR is only needed for handwritten notes or scanned image files.

---

## Manual Installation

If you prefer manual setup instead of the `.bat` file:

```bash
# 1. Navigate to project directory
cd smart-study-agent

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start backend
cd backend
python app.py
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Backend health check |
| POST | `/api/profile` | Save student profile |
| POST | `/api/upload` | Upload study documents |
| POST | `/api/query` | Main AI query endpoint |
| POST | `/api/quiz-score` | Record quiz score |
| GET | `/api/progress` | Get dashboard data |
| POST | `/api/clear-session` | Reset session |

---

## Security Notes

- The `GROQ_API_KEY` is stored **only in the backend `.env` file** and never sent to the browser.
- All user input is sanitised before reaching the AI model.
- Prompt injection attempts are detected and blocked.
- All AI responses are labelled as AI-generated and students are encouraged to verify with official sources.
- Never commit your `.env` file to version control.

---

## Supported File Types

| Type | Format | Notes |
|------|--------|-------|
| PDF | `.pdf` | Text extraction via PyMuPDF |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` | OCR via Tesseract (optional) |
| Text | `.txt`, `.md` | Direct text reading |

**Max file size**: 20 MB per file.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "GROQ_API_KEY not set" error | Ensure `.env` exists and has the correct key |
| Backend won't start | Check Python version (`python --version` must be 3.11+) |
| PDF shows no text | The PDF may be image-based — install Tesseract for OCR |
| CORS error in browser | Ensure backend is running on port 5000 and you're accessing frontend from 5500 |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` inside activated venv |

---

## AI Disclaimer

All content generated by this application is produced by an AI model (Qwen 3 27B via Groq). While the model strives to be accurate, **always verify important academic information** with your teacher, textbook, or official curriculum before relying on it for exams.

---

*Smart Study Generator · Built with Groq + Qwen 3 27B · For educational use*
