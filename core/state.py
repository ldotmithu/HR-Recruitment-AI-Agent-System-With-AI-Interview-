from typing import TypedDict,Optional

class HRApplicationState(TypedDict):
    pdf_path:str
    resume_text:str
    email:str
    job_text:str
    ats_score:float
    resume_summary:Optional[str]
    
    email_sent: bool  # True if an acceptance/rejection email was successfully sent
    decision: Optional[str]  # "Accepted", "Rejected", or "Review"
    
    extraction_error: bool        # True if PDF extraction failed
    scoring_error: bool           # True if ATS scoring failed
    email_error: bool             # True if email sending failed
    error_message: Optional[str]