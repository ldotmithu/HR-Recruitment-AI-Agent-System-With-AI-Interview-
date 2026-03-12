import os
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_webrtc import webrtc_streamer
from eye_tracker import EyeTrackingProcessor


load_dotenv()


st.set_page_config(page_title="HR SmartHire AI", page_icon="🤖", layout="wide")


BACKEND_URL = st.sidebar.text_input("Backend URL", os.getenv("BACKEND_URL", "http://localhost:8000"))
st.sidebar.info("Ensure your FastAPI backend is running.")
st.sidebar.write("🧑‍💻 Developer: Tharmilan")


if "results" not in st.session_state:
    st.session_state.results = []
if "interview_active" not in st.session_state:
    st.session_state.interview_active = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_candidate" not in st.session_state:
    st.session_state.current_candidate = None
if "last_ai_response" not in st.session_state:
    st.session_state.last_ai_response = None
if "candidate_token_data" not in st.session_state:
    st.session_state.candidate_token_data = None
if "question_count" not in st.session_state:
    st.session_state.question_count = 0
if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = False


def process_resume(file, jd):
    try:
        files = {"resume_file": (file.name, file.getvalue(), "application/pdf")}
        data = {"job_description": jd}
        resp = requests.post(f"{BACKEND_URL}/process_resume/", files=files, data=data, timeout=60)
        if resp.status_code == 200:
            res = resp.json()
            res["file_name"] = file.name
            res["ats_score"] = float(res.get("ats_score", 0))
            return res
        return {"file_name": file.name, "ats_score": 0, "error": resp.text}
    except Exception as e:
        return {"file_name": file.name, "ats_score": 0, "error": str(e)}

def save_candidate_to_db(result, job_description):
    payload = {
        "file_name": result["file_name"],
        "email": result.get("email", ""),
        "ats_score": result.get("ats_score", 0),
        "decision": result["decision"],
        "summary": result.get("resume_summary", ""),
        "resume_text": result.get("resume_text", ""),
        "job_description": job_description
    }
    try:
        requests.post(f"{BACKEND_URL}/candidates/", json=payload)
    except Exception as e:
        st.error(f"Failed to save candidate: {e}")

def get_candidates_from_db():
    try:
        resp = requests.get(f"{BACKEND_URL}/candidates/")
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        st.error(f"Failed to fetch candidates: {e}")
        return []

def invite_candidate(candidate_id, name, email):
    payload = {
        "candidate_id": candidate_id,
        "name": name,
        "email": email
    }
    try:
        resp = requests.post(f"{BACKEND_URL}/invite_candidate/", json=payload)
        if resp.status_code == 200:
            st.success(f"Invite sent to {email}!")
            return resp.json().get("link")
        else:
            st.error(f"Failed to send invite: {resp.text}")
    except Exception as e:
        st.error(f"Failed to send invite: {e}")
    return None

def get_ai_response(user_input, candidate_data=None):
    # st.session_state.chat_history.append(f"Candidate: {user_input}") # Moved to send_message
    
    if candidate_data:
        resume_text = candidate_data.get("resume_text", "")
        job_text = candidate_data.get("job_text", "")
    else:
        candidate = st.session_state.current_candidate
        resume_text = candidate.get("resume_text", "") if candidate else ""
        job_text = st.session_state.get("job_description_text", "")

    payload = {
        "resume_text": resume_text,
        "job_text": job_text,
        "chat_history": "\n".join(st.session_state.chat_history),
        "user_input": user_input
    }
    
    try:
        resp = requests.post(f"{BACKEND_URL}/interview/", json=payload)
        if resp.status_code == 200:
            ai_response = resp.json().get("response", "")
            st.session_state.chat_history.append(f"Interviewer: {ai_response}")
            st.session_state.last_ai_response = ai_response
            return ai_response
        else:
            st.error(f"Error: {resp.text}")
            return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def get_feedback(candidate_data):
    if candidate_data:
        resume_text = candidate_data.get("resume_text", "")
        job_text = candidate_data.get("job_text", "")
    else:
       
        candidate = st.session_state.current_candidate
        resume_text = candidate.get("resume_text", "") if candidate else ""
        job_text = st.session_state.get("job_description_text", "")

    payload = {
        "resume_text": resume_text,
        "job_text": job_text,
        "chat_history": "\n".join(st.session_state.chat_history),
        "user_input": "" 
    }
    
    try:
        resp = requests.post(f"{BACKEND_URL}/interview/feedback/", json=payload)
        if resp.status_code == 200:
            feedback = resp.json().get("response", "")
            return feedback
        else:
            st.error(f"Error getting feedback: {resp.text}")
            return None
    except Exception as e:
        st.error(f"Error getting feedback: {e}")
        return None

def text_to_speech(text):
    try:
        resp = requests.post(f"{BACKEND_URL}/tts/", json={"text": text})
        if resp.status_code == 200:
            return resp.content
        else:
            st.error(f"TTS Error: {resp.text}")
            return None
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

def speech_to_text(audio_bytes):
    try:
        files = {"audio_file": ("audio.wav", audio_bytes, "audio/wav")}
        resp = requests.post(f"{BACKEND_URL}/stt/", files=files)
        if resp.status_code == 200:
            return resp.json().get("text", "")
        else:
            st.error(f"STT Error: {resp.text}")
            return ""
    except Exception as e:
        st.error(f"STT Error: {e}")
        return ""

def handle_candidate_answer(answer_text):
    if not answer_text:
        return

    # 1. Append User Answer
    st.session_state.chat_history.append(f"Candidate: {answer_text}")
    
    # 2. Check if we reached the limit (5 responses total)
    if st.session_state.question_count >= 5:
        # End Interview & Get Feedback
        st.session_state.interview_complete = True
        with st.spinner("Generating performance feedback..."):
            feedback = get_feedback(st.session_state.candidate_token_data)
            if feedback:
                st.session_state.chat_history.append(f"System: {feedback}")
                st.session_state.last_ai_response = feedback
    else:
        # Continue Interview
        with st.spinner("AI is thinking..."):
            ai_response = get_ai_response(answer_text, st.session_state.candidate_token_data)
            if ai_response:
                st.session_state.question_count += 1
                audio_content = text_to_speech(ai_response)
                if audio_content:
                    st.session_state.last_audio_content = audio_content

def send_message():
    user_input = st.session_state.user_input
    if user_input:
        handle_candidate_answer(user_input)
        st.session_state.user_input = ""


query_params = st.query_params
token = query_params.get("token")

if token:
    
    st.title("🎤 Live AI Interview")
    
    if not st.session_state.candidate_token_data:
        try:
            resp = requests.get(f"{BACKEND_URL}/candidate/{token}")
            if resp.status_code == 200:
                st.session_state.candidate_token_data = resp.json()
               
                greeting = f"Hello {st.session_state.candidate_token_data['name']}! I'm your AI interviewer. I've reviewed your resume. To start, could you please introduce yourself and tell me about your background?"
                st.session_state.chat_history.append(f"Interviewer: {greeting}")
                st.session_state.last_ai_response = greeting
                st.session_state.question_count = 1 
            else:
                st.error("Invalid or expired interview link.")
                st.stop()
        except Exception as e:
            st.error(f"Error connecting to interview server: {e}")
            st.stop()
            
    # Interview 
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Interview Chat")
        
        # Voice Input
        audio_value = st.audio_input("Record your answer")
        if audio_value and not st.session_state.interview_complete:
            st.write("Processing audio...")
            text = speech_to_text(audio_value.getvalue())
            if text:
                st.success(f"You said: {text}")
                handle_candidate_answer(text)
        
        # Render any new audio response if available
        if "last_audio_content" in st.session_state and st.session_state.last_audio_content:
            st.audio(st.session_state.last_audio_content, format="audio/mp3", autoplay=True)
            st.session_state.last_audio_content = None # Clear after playing
        
        for msg in st.session_state.chat_history:
            if msg.startswith("Interviewer:"):
                st.info(msg)
            else:
                st.success(msg)
                
        if st.session_state.interview_complete:
            st.info("Interview Completed. See feedback above.")
        else:
            st.text_input("Your Answer (Text):", key="user_input", on_change=send_message)

    with col2:
        st.markdown("### Monitoring")
        webrtc_ctx = webrtc_streamer(
            key="eye-tracking",
            video_processor_factory=EyeTrackingProcessor,
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            }
        )
        if webrtc_ctx.video_processor:
            st.write(f"Gaze Status: **{webrtc_ctx.video_processor.gaze_text}**")
            if "LOOKING" in webrtc_ctx.video_processor.gaze_text and webrtc_ctx.video_processor.gaze_text != "LOOKING CENTER":
                st.warning("⚠️ Please look at the screen!")

else:
    st.title("🤖 HR SmartHire AI — Resume Screening")
    st.caption("Upload resumes, analyze ATS scores, auto-categorize candidates, and conduct live AI interviews.")

    # ---------------- UPLOAD & INPUT ----------------
    uploaded_files = st.file_uploader("📂 Upload Resumes (PDF)", type=["pdf"], accept_multiple_files=True)
    job_description = st.text_area("💼 Job Description", placeholder="Paste job description here...", height=150)
    analyze = st.button("🚀 Analyze")

    
    if analyze:
        if not uploaded_files:
            st.error("Please upload PDF resumes.")
        elif not job_description.strip():
            st.error("Please provide a job description.")
        else:
            st.session_state.results = []
            st.session_state.job_description_text = job_description 
            progress = st.progress(0)
            for i, file in enumerate(uploaded_files):
                result = process_resume(file, job_description)

                score = result.get("ats_score", 0)
                if score >= 70:
                    decision = "Accepted"
                elif 50 <= score < 70:
                    decision = "Review"
                else:
                    decision = "Rejected"
                result["decision"] = decision

                # Save to DB via API
                if decision in ["Accepted", "Review"]:
                    save_candidate_to_db(result, job_description)

                st.session_state.results.append(result)
                progress.progress((i+1)/len(uploaded_files))

            st.success("✅ Resume processing completed!")

    #  DASHBOARD 
    candidates_data = get_candidates_from_db()
    
    
    if candidates_data:
        df = pd.DataFrame(candidates_data)
        st.subheader("📊 Results Summary")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total", len(df))
        col2.metric("Accepted", (df["decision"] == "Accepted").sum())
        col3.metric("Review", (df["decision"] == "Review").sum())
        col4.metric("Rejected", (df["decision"] == "Rejected").sum())
        col5.metric("Avg ATS", round(df["ats_score"].mean(), 2))
        st.dataframe(df[["file_name", "ats_score", "decision", "email"]], width="stretch")
        
        st.markdown("---")
        st.subheader("📧 Send Interview Invites")
        
        # Filter for Accepted/Review
        invite_candidates = [c for c in candidates_data if c["decision"] in ["Accepted", "Review"]]
        
        if invite_candidates:
            for cand in invite_candidates:
                c_id = cand["id"]
                c_name = cand["file_name"]
                c_email = cand["email"]
                c_decision = cand["decision"]
                
                col1, col2, col3 = st.columns([3, 2, 2])
                col1.write(f"**{c_name}** ({c_decision})")
                col2.write(c_email if c_email else "No Email")
                if col3.button(f"Send Invite to {c_name}", key=f"invite_{c_id}"):
                    if c_email:
                        link = invite_candidate(c_id, c_name, c_email)
                        if link:
                            st.info(f"Link generated: {link}")
                    else:
                        st.error("No email found for this candidate.")
        else:
            st.info("No candidates available for interview invites yet.")

    else:
        st.info("Upload resumes and click *Analyze* to start.")
