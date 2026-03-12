import os
import shutil
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from datetime import datetime, timedelta

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import speech_recognition as sr
from gtts import gTTS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

from core.graph import hr_app_workflow
from core.state import HRApplicationState
from core.llm_chains import interview_chain
from pydantic import BaseModel

app = FastAPI(title="HR AI Application Backend", version="1.0.0")

origins = [
    "http://localhost",
    "http://localhost:8501", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_FILES_DIR = Path("backend/temp_files")
TEMP_FILES_DIR.mkdir(parents=True, exist_ok=True)

executor = ThreadPoolExecutor(max_workers=4) 

def get_executor():
    """Dependency for getting the shared ThreadPoolExecutor."""
    return executor

# --- DATABASE SETUP ---
DB_PATH = Path("..") / "hr_smarthire.db"
if not DB_PATH.parent.exists():
    DB_PATH = Path("hr_smarthire.db")

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        email TEXT,
        ats_score REAL,
        decision TEXT,
        summary TEXT,
        resume_text TEXT,
        job_description TEXT,
        token TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Check/Add columns if missing (simple migration)
    try:
        cursor.execute("SELECT token FROM candidates LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE candidates ADD COLUMN token TEXT")
    
    try:
        cursor.execute("SELECT resume_text FROM candidates LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE candidates ADD COLUMN resume_text TEXT")
        
    try:
        cursor.execute("SELECT job_description FROM candidates LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE candidates ADD COLUMN job_description TEXT")
    
    try:
        cursor.execute("SELECT created_at FROM candidates LIMIT 1")
    except sqlite3.OperationalError:
        # SQLite doesn't support DEFAULT CURRENT_TIMESTAMP in ALTER TABLE
        # Add column with NULL default, then update existing rows
        cursor.execute("ALTER TABLE candidates ADD COLUMN created_at TIMESTAMP")
        cursor.execute("UPDATE candidates SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        
    conn.commit()
    conn.close()

init_db()

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down... Cleaning up temporary files.")
    if TEMP_FILES_DIR.exists():
        shutil.rmtree(TEMP_FILES_DIR)
        print(f"Cleaned up {TEMP_FILES_DIR}")
    executor.shutdown(wait=True)
    print("ThreadPoolExecutor shut down.")

@app.post("/process_resume/")
async def process_resume(
    resume_file: UploadFile = File(...),
    job_description: str = Form(...),
    executor: ThreadPoolExecutor = Depends(get_executor)
):
    """
    Processes a resume PDF against a job description using the LangGraph workflow.
    """
    if not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    unique_filename = f"{uuid.uuid4()}_{resume_file.filename}"
    pdf_path = TEMP_FILES_DIR / unique_filename

    try:
        with open(pdf_path, "wb") as buffer:
            shutil.copyfileobj(resume_file.file, buffer)
        print(f"Received and saved PDF to: {pdf_path}")
        
        initial_state: HRApplicationState = {
            'pdf_path': str(pdf_path),
            'job_text': job_description,
            'resume_text': '',
            'email': '',
            'ats_score': 0.0,
            'resume_summary': None,
            'extraction_error': False,
            'scoring_error': False,
            'email_error': False,
            'error_message': None,
            'email_sent': False, 
        }

        print("Invoking LangGraph workflow in background...")
        future = executor.submit(hr_app_workflow.invoke, initial_state)
        final_state = future.result() 
        print("LangGraph workflow completed.")
        
        # --- NEW: Organize Resume by Status ---
        # Enforce score-based decision logic (Accept >= 70, Review 50-70, Reject < 50)
        score = final_state.get("ats_score", 0.0)
        if score >= 70:
            decision = "Accepted"
        elif score >= 50:
            decision = "Review"
        else:
            decision = "Rejected"
            
        final_state["decision"] = decision
        status_folder = Path("resumes") / decision.lower()
        status_folder.mkdir(parents=True, exist_ok=True)
        
        final_resume_path = status_folder / resume_file.filename
        if final_resume_path.exists():
            final_resume_path = status_folder / f"{uuid.uuid4().hex[:8]}_{resume_file.filename}"
            
        shutil.copy2(pdf_path, final_resume_path)
        print(f"Resume saved to status folder: {final_resume_path}")
        # ---------------------------------------

        return JSONResponse(content=final_state)

    except Exception as e:
        print(f"Unhandled error during resume processing: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    finally:
        if pdf_path.exists():
            os.remove(pdf_path)
            print(f"Cleaned up temporary PDF: {pdf_path}")

class InterviewRequest(BaseModel):
    resume_text: str
    job_text: str
    chat_history: str
    user_input: str

@app.post("/interview/")
async def interview_endpoint(request: InterviewRequest):
    if not interview_chain:
         raise HTTPException(status_code=500, detail="LLM not initialized.")
    
    try:
        response = interview_chain.invoke({
            "resume_text": request.resume_text,
            "job_text": request.job_text,
            "chat_history": request.chat_history,
            "user_input": request.user_input
        })
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stt/")
async def speech_to_text(audio_file: UploadFile = File(...)):
    try:
        recognizer = sr.Recognizer()
        audio_path = TEMP_FILES_DIR / f"{uuid.uuid4()}_{audio_file.filename}"
        
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
            
        with sr.AudioFile(str(audio_path)) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
        
        os.remove(audio_path)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT Error: {e}")

class TTSRequest(BaseModel):
    text: str

@app.post("/tts/")
async def text_to_speech(request: TTSRequest):
    try:
        tts = gTTS(text=request.text, lang='en')
        filename = f"{uuid.uuid4()}.mp3"
        filepath = TEMP_FILES_DIR / filename
        tts.save(str(filepath))
        return FileResponse(filepath, media_type="audio/mpeg", filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Error: {e}")

# --- DB & Remote Access Endpoints ---

class CandidateCreate(BaseModel):
    file_name: str
    email: str
    ats_score: float
    decision: str
    summary: str
    resume_text: str
    job_description: str

@app.post("/candidates/")
async def create_candidate(candidate: CandidateCreate):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO candidates (file_name, email, ats_score, decision, summary, resume_text, job_description) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (candidate.file_name, candidate.email, candidate.ats_score, candidate.decision, candidate.summary, candidate.resume_text, candidate.job_description)
        )
        conn.commit()
        conn.close()
        return {"message": "Candidate saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB Error: {e}")

@app.get("/candidates/")
async def get_candidates(days: int = None):
    """
    Get candidates from database.
    If days parameter is provided, only return candidates from the last X days.
    If days is None, return all candidates.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        if days is None:
            cursor.execute("SELECT id, file_name, email, ats_score, decision, summary, created_at FROM candidates ORDER BY created_at DESC")
        else:
            cursor.execute(
                "SELECT id, file_name, email, ats_score, decision, summary, created_at FROM candidates WHERE created_at >= datetime('now', '-' || ? || ' days') ORDER BY created_at DESC",
                (days,)
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        candidates = []
        for row in rows:
            candidates.append({
                "id": row[0],
                "file_name": row[1],
                "email": row[2],
                "ats_score": row[3],
                "decision": row[4],
                "summary": row[5],
                "created_at": row[6] if len(row) > 6 else None
            })
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB Error: {e}")

class InviteCandidateRequest(BaseModel):
    candidate_id: int
    name: str
    email: str

@app.post("/invite_candidate/")
async def invite_candidate(request: InviteCandidateRequest):
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    if not sender_email or not sender_password:
        raise HTTPException(status_code=500, detail="Email credentials not configured.")

    token = str(uuid.uuid4())
    link = f"http://localhost:8501/?token={token}"

    try:
        # Update DB with token
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("UPDATE candidates SET token=? WHERE id=?", (token, request.candidate_id))
        conn.commit()
        conn.close()
        
        # Send Email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = request.email
        msg['Subject'] = "Invitation to AI Mock Interview"

        # Plain text version
        plain_text = f"""Dear {request.name},

Congratulations! You have been selected for the next round of our recruitment process.

We are excited to invite you to an AI-powered mock interview. This is a unique opportunity for us to learn more about your skills and experience in an interactive format.

To start your interview, please click the link below:
{link}

Please ensure you have a stable internet connection and are in a quiet environment before starting.

Best regards,
HR Team
"""

        # HTML version
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        h1 {{ margin: 0; font-size: 24px; }}
        p {{ margin: 15px 0; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #667eea; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 20px 0; }}
        .button:hover {{ background-color: #5a6fd6; }}
        .note {{ background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Interview Invitation</h1>
        </div>
        <div class="content">
            <p>Dear {request.name},</p>
            
            <p><strong>Congratulations!</strong> You have been selected for the next round of our recruitment process.</p>
            
            <p>We are excited to invite you to an <strong>AI-powered mock interview</strong>. This is a unique opportunity for us to learn more about your skills and experience in an interactive format.</p>
            
            <div style="text-align: center;">
                <a href="{link}" class="button">Start Interview Now</a>
            </div>
            
            <p>If the button above doesn't work, you can copy and paste the following link into your browser:</p>
            <p style="word-break: break-all; color: #667eea;">{link}</p>
            
            <div class="note">
                <p style="margin: 0;"><strong>📝 Important Tips:</strong></p>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>Ensure you have a stable internet connection</li>
                    <li>Find a quiet environment with minimal background noise</li>
                    <li>Allow access to your microphone when prompted</li>
                </ul>
            </div>
            
            <p>Best regards,<br>
            <strong>HR Team</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message from our AI-powered recruitment system.</p>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(plain_text, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        return {"message": "Invite sent successfully", "link": link}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@app.get("/candidate/{token}")
async def get_candidate_by_token(token: str):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT file_name, email, resume_text, job_description FROM candidates WHERE token=?", (token,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "name": row[0],
                "email": row[1],
                "resume_text": row[2],
                "job_text": row[3]
            }
        else:
            raise HTTPException(status_code=404, detail="Candidate not found or invalid token.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {e}")

@app.post("/reset-dashboard/")
async def reset_dashboard(days: int = None):
    """
    Reset dashboard by clearing old candidate data.
    If days is provided, delete candidates older than that many days.
    If days is None, delete ALL candidates.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        if days is None:
            # Delete ALL candidates
            cursor.execute("DELETE FROM candidates")
            deleted = cursor.rowcount
        else:
            # Delete candidates older than X days
            cursor.execute(
                "DELETE FROM candidates WHERE created_at < datetime('now', '-' || ? || ' days')",
                (days,)
            )
            deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return {"message": f"Dashboard reset successfully. Deleted {deleted} candidates."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset Error: {e}")

@app.get("/")
async def root():
    return {"message": "HR AI Application Backend is running! Use /docs for API documentation."}
