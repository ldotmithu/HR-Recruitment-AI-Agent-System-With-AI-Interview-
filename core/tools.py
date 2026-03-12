from langchain_core.tools import tool
import PyPDF2
from sentence_transformers import SentenceTransformer,util
from email.message import EmailMessage
import re ,os 
import smtplib
from dotenv import load_dotenv
load_dotenv()
try:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("model loaded successfully")
except Exception as e:
    raise e 

@tool
def extract_text_from_pdf(pdf_path):
    """Extract text and email address from a PDF resume."""
    try:
        with open(pdf_path,"rb") as f:
            reader = PyPDF2.PdfReader(f)
            text =""
            for page in reader.pages:
                text += page.extract_text()
        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",text)
        email = email_match.group(0) if email_match else ""
        
        return {"resume_text":text,"email":email,"extraction_error":False,"error_message":None}
    except Exception as e:
        return {"resume_text":"","email":"","extraction_error":True,"error_message":e}    

@tool
def llm_ats_score(resume_text:str,job_text:str):
    """
    Compute semantic similarity between resume and job description using embeddings.
    Returns an ATS score between 0–100.
    """
    if not model:
        error_msg = "SentenceTransformer model not loaded for ATS scoring."
        return {"ats_score":0.0,"scoring_error":True,"error_message":error_msg}
    
    try:
        embaddings = model.encode([resume_text,job_text])
        similarity= util.cos_sim(embaddings[0],embaddings[1]).item()
        score = round(similarity*100,2)
        return{"ats_score":score,"scoring_error":False,"error_message":None}
    except Exception as e :
        return{"ats_score":0.0,"scoring_error":True,"error_message":e}


@tool
def send_rejection_email(email:str):
    """Send a polite rejection email if ATS score is low."""
    sender = os.getenv("EMAIL_SENDER")
    password= os.getenv("EMAIL_PASSWORD")
    
    if not sender or not password:
        error_msg = "Email sender or password not configured in .env"
        return {"email_sent": False, "email_error": True, "error_message": error_msg}
    
    try:
        msg = EmailMessage()
        msg["Subject"] = "Update on Your Job Application"
        msg["From"] = sender
        msg["To"] = email
        
        # Plain text version
        plain_text = """Dear Candidate,

Thank you for taking the time to apply for the position with our organization. We truly appreciate your interest in joining our team.

After careful consideration of your application and resume, we regret to inform you that we will not be moving forward with your candidacy at this time. While your qualifications are impressive, we have decided to pursue candidates whose experience more closely aligns with the specific requirements of this role.

We encourage you to continue monitoring our career opportunities, as we frequently have new openings that may be a better match for your skills and experience.

We wish you the very best in your job search and future career endeavors.

Warm regards,
HR Recruitment Team
"""
        
        # HTML version
        html_content = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
        h1 { margin: 0; font-size: 24px; }
        p { margin: 15px 0; }
        .highlight { background-color: #f0f0f0; padding: 15px; border-left: 4px solid #667eea; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Update on Your Application</h1>
        </div>
        <div class="content">
            <p>Dear Candidate,</p>
            
            <p>Thank you for taking the time to apply for the position with our organization. We truly appreciate your interest in joining our team and the effort you put into your application.</p>
            
            <p>After careful consideration of your application and resume, we regret to inform you that <strong>we will not be moving forward with your candidacy at this time</strong>. While your qualifications are impressive, we have decided to pursue candidates whose experience more closely aligns with the specific requirements of this role.</p>
            
            <div class="highlight">
                <p style="margin: 0;"><strong>💡 We encourage you to:</strong></p>
                <ul style="margin: 10px 0;">
                    <li>Continue monitoring our career opportunities</li>
                    <li>Apply for future positions that match your expertise</li>
                    <li>Connect with us on professional networks</li>
                </ul>
            </div>
            
            <p>We wish you the very best in your job search and future career endeavors. Thank you once again for considering us as a potential employer.</p>
            
            <p>Warm regards,<br>
            <strong>HR Recruitment Team</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message from our AI-powered recruitment system.</p>
        </div>
    </div>
</body>
</html>
"""
        
        msg.set_content(plain_text)
        msg.add_alternative(html_content, subtype='html')

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"Rejection email sent to: {email}")
        return {"email_sent": True, "email_error": False, "error_message": None}
    except Exception as e:
        error_msg = f"Error sending rejection email to {email}: {e}"
        print(f"{error_msg}")
        return {"email_sent": False, "email_error": True, "error_message": error_msg}

@tool
def send_acceptance_email(email:str):
    """Send an acceptance email if ATS score is high."""
    sender = os.getenv("EMAIL_SENDER")
    password= os.getenv("EMAIL_PASSWORD")
    
    if not sender or not password:
        error_msg = "Email sender or password not configured in .env"
        return {"email_sent": False, "email_error": True, "error_message": error_msg}
    
    try:
        msg = EmailMessage()
        msg["Subject"] = "🎉 Congratulations! Next Steps in Your Application Process"
        msg["From"] = sender
        msg["To"] = email
        
        # Plain text version
        plain_text = """Dear Candidate,

Congratulations! We are pleased to inform you that your application has been successfully shortlisted.

After reviewing your resume and qualifications, we are impressed with your background and believe you could be an excellent fit for our team. Your skills and experience align well with the requirements of the position.

NEXT STEPS:
- You will receive a separate email shortly with details about the online interview process
- The interview will be conducted through our AI-powered interview platform
- Please prepare to discuss your experience, skills, and career aspirations
- Make sure to review the job description thoroughly before the interview

We are excited about the possibility of you joining our team and look forward to learning more about you in the interview.

If you have any questions in the meantime, please don't hesitate to reach out.

Best regards,
HR Recruitment Team
"""
        
        # HTML version
        html_content = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }
        .header { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
        h1 { margin: 0; font-size: 24px; }
        p { margin: 15px 0; }
        .success-box { background: linear-gradient(135deg, #e0f7e9 0%, #c8f0d8 100%); padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #38ef7d; }
        .next-steps { background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .next-steps ul { margin: 10px 0; padding-left: 20px; }
        .next-steps li { margin: 8px 0; }
        .emoji { font-size: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="emoji">🎉</span>
            <h1>Congratulations!</h1>
            <p style="margin: 10px 0 0 0; font-size: 16px;">Your Application Has Been Shortlisted</p>
        </div>
        <div class="content">
            <p>Dear Candidate,</p>
            
            <div class="success-box">
                <p style="margin: 0; font-size: 18px;"><strong>✅ Great News!</strong></p>
                <p style="margin: 10px 0 0 0;">We are pleased to inform you that your application has been <strong>successfully shortlisted</strong> for the next round of our recruitment process.</p>
            </div>
            
            <p>After carefully reviewing your resume and qualifications, we are impressed with your background and believe you could be an excellent fit for our team. Your skills and experience align well with the requirements of the position.</p>
            
            <div class="next-steps">
                <p style="margin: 0 0 10px 0;"><strong>📋 NEXT STEPS:</strong></p>
                <ul>
                    <li>You will receive a <strong>separate email shortly</strong> with details about the online interview process</li>
                    <li>The interview will be conducted through our <strong>AI-powered interview platform</strong></li>
                    <li>Please prepare to discuss your experience, skills, and career aspirations</li>
                    <li>Make sure to review the job description thoroughly before the interview</li>
                </ul>
            </div>
            
            <p>We are excited about the possibility of you joining our team and look forward to learning more about you in the interview.</p>
            
            <p>If you have any questions in the meantime, please don't hesitate to reach out.</p>
            
            <p>Best regards,<br>
            <strong>HR Recruitment Team</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message from our AI-powered recruitment system.</p>
        </div>
    </div>
</body>
</html>
"""
        
        msg.set_content(plain_text)
        msg.add_alternative(html_content, subtype='html')

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"Acceptance email sent to: {email}")
        return {"email_sent": True, "email_error": False, "error_message": None}
    except Exception as e:
        error_msg = f"Error sending acceptance email to {email}: {e}"
        print(f"{error_msg}")
        return {"email_sent": False, "email_error": True, "error_message": error_msg}
    
    
@tool
def send_review_email(email:str):
    """Send an email informing the candidate that their resume is under review."""
    sender = os.getenv("EMAIL_SENDER")
    password= os.getenv("EMAIL_PASSWORD")
    
    if not sender or not password:
        error_msg = "Email sender or password not configured in .env"
        return {"email_sent": False, "email_error": True, "error_message": error_msg}
    
    try:
        msg = EmailMessage()
        msg["Subject"] = "Application Received - Under Review"
        msg["From"] = sender
        msg["To"] = email
        
        # Plain text version
        plain_text = """Dear Candidate,

Thank you for submitting your application for the position with our organization. We are writing to confirm that we have successfully received your resume and application materials.

Your application is currently under review by our recruitment team. We are carefully evaluating all candidates to ensure we find the best match for this role.

WHAT TO EXPECT:
- Our team will thoroughly review your qualifications and experience
- You can expect to hear back from us within 5-7 business days
- We will contact you via email with an update on your application status
- If your profile matches our requirements, we will reach out with next steps

We appreciate your patience during this process and your interest in joining our team.

Thank you for considering this opportunity with us.

Best regards,
HR Recruitment Team
"""
        
        # HTML version
        html_content = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }
        .header { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
        h1 { margin: 0; font-size: 24px; }
        p { margin: 15px 0; }
        .info-box { background-color: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4facfe; }
        .timeline { background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .timeline ul { margin: 10px 0; padding-left: 20px; }
        .timeline li { margin: 8px 0; }
        .emoji { font-size: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="emoji">📧</span>
            <h1>Application Received</h1>
            <p style="margin: 10px 0 0 0; font-size: 16px;">We're Reviewing Your Profile</p>
        </div>
        <div class="content">
            <p>Dear Candidate,</p>
            
            <p>Thank you for submitting your application for the position with our organization. We are writing to confirm that we have <strong>successfully received</strong> your resume and application materials.</p>
            
            <div class="info-box">
                <p style="margin: 0; font-size: 18px;"><strong>🔍 Current Status: Under Review</strong></p>
                <p style="margin: 10px 0 0 0;">Your application is currently being carefully evaluated by our recruitment team. We are reviewing all candidates to ensure we find the best match for this role.</p>
            </div>
            
            <div class="timeline">
                <p style="margin: 0 0 10px 0;"><strong>⏱️ WHAT TO EXPECT:</strong></p>
                <ul>
                    <li>Our team will thoroughly review your qualifications and experience</li>
                    <li>You can expect to hear back from us <strong>within 5-7 business days</strong></li>
                    <li>We will contact you via email with an update on your application status</li>
                    <li>If your profile matches our requirements, we will reach out with next steps</li>
                </ul>
            </div>
            
            <p>We appreciate your patience during this process and your interest in joining our team.</p>
            
            <p>Thank you for considering this opportunity with us.</p>
            
            <p>Best regards,<br>
            <strong>HR Recruitment Team</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message from our AI-powered recruitment system.</p>
        </div>
    </div>
</body>
</html>
"""
        
        msg.set_content(plain_text)
        msg.add_alternative(html_content, subtype='html')

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"Review email sent to: {email}")
        return {"email_sent": True, "email_error": False, "error_message": None}
    except Exception as e:
        error_msg = f"Error sending review email to {email}: {e}"
        print(f"{error_msg}")
        return {"email_sent": False, "email_error": True, "error_message": error_msg}