# HR SmartHire AI Assistant 🤖📄

## Introduction ✨
The **HR SmartHire AI Assistant** is an enterprise-grade recruitment automation platform designed to streamline the hiring process. Built with a high-performance **FastAPI backend** and a modern, real-time **HTML/CSS/JS frontend**, it leverages **Generative AI**, **Computer Vision**, and **Semantic Search** to transform hiring from manual screening to intelligent, automated decision-making.

The system features a professional dark-themed dashboard with glassmorphism design, real-time eye tracking during interviews, and automated scheduling with Google Calendar.

---

## 📸 Workflow Visualization
The system follows a professional 7-step recruitment pipeline orchestrated by a robust AI state machine.

1. **Resume Upload** 📄: Batch upload of PDF resumes.
2. **JD Integration** 📋: Job description alignment for semantic matching.
3. **ATS Scoring** 🎯: Semantic similarity scoring (0-100%) via embeddings.
4. **Filtering** 🔍: Automatic categorization (Shortlisted / Review / Rejected).
5. **AI Interview** 🎤: 5-question dynamic mock interview session.
6. **Eye Tracking** 👁️: Real-time gaze analysis via MediaPipe for behavioral integrity.
7. **AI Feedback** 📊: Detailed performance reports with communication and technical scores.

---

## 🚀 Key Features

### 1. Smart Resume Analysis & ATS 📄
- **Batch Processing**: Upload multiple PDF resumes simultaneously.
- **Semantic Matching**: High-precision ATS scoring comparing resumes against Job Descriptions using **Sentence Transformers**.
- **Detailed Metrics**: Automatic assessment of **Skill Match**, **Experience Match**, and identifying **Missing Keywords**.

### 2. Live AI Interview Engine 🎤
- **Dynamic Questioning**: Generates 5 personalized questions based on the candidate's specific background and JD.
- **Voice-Enabled Interaction**: Supports real-time voice-to-text input (Web Speech API).
- **TTS Feedback**: The AI "speaks" questions using text-to-speech for a more human-like experience.

### 3. Professional HR Dashboard 📊
- **Enterprise UI**: Sleek dark mode interface with glassmorphism and smooth animations.
- **Workflow Pipeline**: Visual tracking of candidate progress through the 7-step recruitment funnel.
- **Candidate Analytics**: Comprehensive table with ATS scores, category badges, and quick-action buttons.
- **Google Calendar Integration**: Schedule interviews directly from the dashboard; candidates receive an invite with an "Add to Google Calendar" button.

### 4. Integrity & Behavioral Analysis 👁️
- **Gaze Tracking**: Real-time eye movement monitoring using **MediaPipe FaceMesh**.
- **Integrity Metrics**: Calculates Eye Contact % and tracks "Look-Aways" during the interview session.
- **Event Logging**: Behavioral events are logged with timestamps for HR review.

---

## 🏗️ System Architecture

### Backend (FastAPI + LangGraph)
- **LangGraph Workflow**: Orchestrates the recruitment state machine for parsing, scoring, and decision-making.
- **SQLite Database**: Persistent storage for candidate profiles, ATS results, and generated interview tokens.
- **Service Layer**: Handles PDF extraction, Email automation (SMTP), and LLM integration (Groq/Llama).

### Frontend (HTML5 / CSS3 / Vanilla JS)
- **Real-time UI**: A responsive, multi-page application with no heavy frameworks for maximum performance.
- **Computer Vision Layer**: Direct browser-based eye tracking using MediaPipe (no server-side video processing required).
- **Authentication**: Token-based login for HR administrators.

---

## 🔧 Setup & Installation

### Prerequisites
- **Python 3.10+**
- **Groq API Key**
- **Gmail App Password** (for automated email/calendar invites)

### 1. Clone & Environment Setup
```bash

python -m venv venv

```
```bash

venv\Scripts\activate

```
```bash

pip install -r requirements.txt

```

### 2. Configuration (`.env`)
Create a `.env` file in the root directory:
```ini
GROQ_API_KEY="your_groq_api_key"
EMAIL_SENDER="your_email@gmail.com"
EMAIL_PASSWORD="your_app_password"
BACKEND_URL="http://localhost:8000"
```

---

### ▶️ Execution

#### Step 1: Start the Backend (FastAPI)
```bash
uvicorn backend.main:app --reload --port 8000
```

#### Step 2: Start the Frontend (HTTP Server)
```bash
cd frontend
python -m http.server 5500
```
Then open: **http://localhost:5500**

---

### 🗑️ Clear All Candidates

Deletes **ALL** candidate records from the database:

```bash
curl -X POST "http://localhost:8000/reset-dashboard/"
```

**Response:**
```json
{
  "message": "Dashboard reset successfully. Deleted {n} candidates."
}
```

## 📊 View Candidates

### Get all candidates
```bash
curl "http://localhost:8000/candidates/"
```
### Get only today's candidates
```bash
curl "http://localhost:8000/candidates/?days=1"
```

---
## 📂 Project Structure
```text
HR-Recruitment-AI-Agent-System/
├── backend/
│   ├── main.py             # API entry point (FastAPI)
│   ├── core/
│   │   ├── graph.py        # LangGraph recruitment workflow
│   │   ├── tools.py        # PDF/Email utility tools
│   │   ├── state.py        # State definitions
│   │   └── llm_chains.py   # AI prompts & chain config
│   └── hr_smarthire.db     # SQLite database
├── frontend/
│   ├── index.html          # Login Page
│   ├── dashboard.html      # HR Dashboard
│   ├── interview.html      # AI Interview Room
│   ├── css/
│   │   └── styles.css      # Enterprise Design System
│   └── js/
│       ├── auth.js         # Session & Auth logic
│       ├── dashboard.js    # Upload & ATS control
│       └── interview.js    # AI Chat & Gaze Tracking
└── requirements.txt
```

---

## 📜 License
Licensed under the **MIT License**.

## 📬 Contact
Built with ❤️ by **Tharmilan**
- Email: selventhirantharmilan@gmail.com

Happy Hiring! 🚀