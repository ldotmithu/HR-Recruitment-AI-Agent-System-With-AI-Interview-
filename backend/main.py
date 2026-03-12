import os
import shutil
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from datetime import datetime, timedelta
import urllib.parse

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import speech_recognition as sr
from gtts import gTTS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydub import AudioSegment

load_dotenv()

from core.graph import hr_app_workflow
from core.state import HRApplicationState
from core.llm_chains import interview_chain, feedback_chain
from pydantic import BaseModel

app = FastAPI(title="HR AI Application Backend", version="1.0.0")

origins = [
    "http://localhost",
    "http://localhost:8501",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        cursor.execute("ALTER TABLE candidates ADD COLUMN created_at TIMESTAMP")
        cursor.execute("UPDATE candidates SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        
    try:
        cursor.execute("SELECT skill_match FROM candidates LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE candidates ADD COLUMN skill_match REAL DEFAULT 0")
        
    try:
        cursor.execute("SELECT experience_match FROM candidates LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE candidates ADD COLUMN experience_match REAL DEFAULT 0")
        
    try:
        cursor.execute("SELECT missing_keywords FROM candidates LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE candidates ADD COLUMN missing_keywords TEXT DEFAULT ''")
        
    conn.commit()
    conn.close()

init_db()

# ── Login Endpoint ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
async def login(request: LoginRequest):
    if request.username == "admin" and request.password == "admin":
        import secrets
        token = secrets.token_hex(32)
        return {"success": True, "token": token, "username": request.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")

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
        
        # Compute extra analytics fields
        resume_text = final_state.get("resume_text", "")
        jd_lower = job_description.lower()
        resume_lower = resume_text.lower()
        
        # Extract job keywords (simple extraction)
        import re as _re
        jd_words = set(_re.findall(r'\b[a-zA-Z]{4,}\b', job_description))
        resume_words = set(_re.findall(r'\b[a-zA-Z]{4,}\b', resume_text))
        common = jd_words & resume_words
        skill_match = round((len(common) / max(len(jd_words), 1)) * 100, 1)
        
        # Experience match: look for year mentions in resume
        years_found = _re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', resume_lower)
        exp_years = max([int(y) for y in years_found], default=0) if years_found else 0
        # Try to find required years in JD
        jd_years = _re.findall(r'(\d+)\+?\s*(?:years?|yrs?)', jd_lower)
        required_years = max([int(y) for y in jd_years], default=3) if jd_years else 3
        experience_match = min(round((exp_years / max(required_years, 1)) * 100, 1), 100.0)
        
        missing = list(jd_words - resume_words)[:10]  # Top 10 missing keywords
        
        result = dict(final_state)
        result["skill_match"] = skill_match
        result["experience_match"] = experience_match
        result["missing_keywords"] = ", ".join(sorted(missing))
        
        # --- NEW: Organize Resume by Status ---
        # Enforce score-based decision logic (Accept >= 70, Review 50-70, Reject < 50)
        score = result.get("ats_score", 0.0)
        if score >= 70:
            decision = "Accepted"
        elif score >= 50:
            decision = "Review"
        else:
            decision = "Rejected"
            
        result["decision"] = decision
        status_folder = Path("resumes") / decision.lower()
        status_folder.mkdir(parents=True, exist_ok=True)
        
        # Use original filename for the final storage
        final_resume_path = status_folder / resume_file.filename
        
        # If file already exists, add a unique prefix to avoid overwriting
        if final_resume_path.exists():
            final_resume_path = status_folder / f"{uuid.uuid4().hex[:8]}_{resume_file.filename}"
            
        shutil.copy2(pdf_path, final_resume_path)
        print(f"Resume saved to status folder: {final_resume_path}")
        # ---------------------------------------

        return JSONResponse(content=result)

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

@app.post("/interview/feedback/")
async def interview_feedback_endpoint(request: InterviewRequest):
    if not feedback_chain:
         raise HTTPException(status_code=500, detail="LLM not initialized.")
    
    try:
        response = feedback_chain.invoke({
            "resume_text": request.resume_text,
            "job_text": request.job_text,
            "chat_history": request.chat_history
        })
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stt/")
async def speech_to_text(audio_file: UploadFile = File(...)):
    raw_path = TEMP_FILES_DIR / f"raw_{uuid.uuid4()}_{audio_file.filename}"
    wav_path = TEMP_FILES_DIR / f"proc_{uuid.uuid4()}.wav"
    
    try:
        # 1. Save uploaded file
        with open(raw_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # 2. Convert to standard WAV using pydub
        try:
            audio = AudioSegment.from_file(str(raw_path))
            # Export as 16kHz, mono, WAV (best for STT)
            audio.export(str(wav_path), format="wav", parameters=["-ac", "1", "-ar", "16000"])
        except Exception as conv_err:
            print(f"Audio conversion failed: {conv_err}")
            # Fallback: try to use the raw file if it might be a valid WAV already
            shutil.copy(raw_path, wav_path)

        # 3. Recognize speech
        recognizer = sr.Recognizer()
        with sr.AudioFile(str(wav_path)) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
        
        return {"text": text}
    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")
        return {"text": ""}
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        raise HTTPException(status_code=500, detail=f"STT Service Error: {e}")
    except Exception as e:
        print(f"Unexpected STT Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"STT Error: {str(e)}")
    finally:
        # Cleanup
        if raw_path.exists():
            os.remove(raw_path)
        if wav_path.exists():
            os.remove(wav_path)

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



class CandidateCreate(BaseModel):
    file_name: str
    email: str
    ats_score: float
    decision: str
    summary: str
    resume_text: str
    job_description: str
    skill_match: float = 0.0
    experience_match: float = 0.0
    missing_keywords: str = ""

@app.post("/candidates/")
async def create_candidate(candidate: CandidateCreate):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO candidates (file_name, email, ats_score, decision, summary, resume_text, job_description, skill_match, experience_match, missing_keywords) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (candidate.file_name, candidate.email, candidate.ats_score, candidate.decision, candidate.summary, candidate.resume_text, candidate.job_description, candidate.skill_match, candidate.experience_match, candidate.missing_keywords)
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
            cursor.execute("SELECT id, file_name, email, ats_score, decision, summary, created_at, skill_match, experience_match, missing_keywords, resume_text, job_description FROM candidates ORDER BY created_at DESC")
        else:
            cursor.execute(
                "SELECT id, file_name, email, ats_score, decision, summary, created_at, skill_match, experience_match, missing_keywords, resume_text, job_description FROM candidates WHERE created_at >= datetime('now', '-' || ? || ' days') ORDER BY created_at DESC",
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
                "created_at": row[6] if len(row) > 6 else None,
                "skill_match": row[7] if len(row) > 7 else 0,
                "experience_match": row[8] if len(row) > 8 else 0,
                "missing_keywords": row[9] if len(row) > 9 else "",
                "resume_text": row[10] if len(row) > 10 else "",
                "job_description": row[11] if len(row) > 11 else ""
            })
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB Error: {e}")

class InviteCandidateRequest(BaseModel):
    candidate_id: int
    name: str
    email: str
    interview_date: str
    interview_time: str

@app.post("/invite_candidate/")
async def invite_candidate(request: InviteCandidateRequest):
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    if not sender_email or not sender_password:
        raise HTTPException(status_code=500, detail="Email credentials not configured.")

    token = str(uuid.uuid4())
    link = f"http://localhost:5500/interview.html?token={token}"

    # Generate Google Calendar Link
    try:
        dt_str = f"{request.interview_date} {request.interview_time}"
        start_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=45)
        
        # Google Calendar format: YYYYMMDDTHHMMSS
        gcal_start = start_dt.strftime("%Y%m%dT%H%M%S")
        gcal_end = end_dt.strftime("%Y%m%dT%H%M%S")
        
        event_title = urllib.parse.quote("AI Mock Interview - SmartHire AI")
        event_details = urllib.parse.quote(f"Your personal AI interview link: {link}\n\nPlease ensure you are in a quiet environment and have your camera enabled.")
        gcal_link = f"https://www.google.com/calendar/render?action=TEMPLATE&text={event_title}&dates={gcal_start}/{gcal_end}&details={event_details}&location=Remote"
    except Exception as e:
        print(f"Calendar link error: {e}")
        gcal_link = "#"

    try:
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

        
        plain_text = f"""Dear {request.name},

Congratulations! You have been selected for the next round of our recruitment process.

We are excited to invite you to an AI-powered mock interview. This is a unique opportunity for us to learn more about your skills and experience in an interactive format.

To start your interview, please click the link below:
{link}

Please ensure you have a stable internet connection and are in a quiet environment before starting.

Best regards,
HR Team
"""

        
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
            
            <div style="text-align: center; margin-top: 10px;">
                <a href="{gcal_link}" target="_blank" style="color: #667eea; text-decoration: none; font-size: 14px; font-weight: bold;">📅 Add to Google Calendar</a>
            </div>
            
            <p><strong>Scheduled Time:</strong> {request.interview_date} at {request.interview_time}</p>

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
            
            cursor.execute("DELETE FROM candidates")
            deleted = cursor.rowcount
        else:
            
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
