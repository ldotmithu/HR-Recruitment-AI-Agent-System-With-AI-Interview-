import requests
import os
import time

BACKEND_URL = "http://localhost:8000"

def test_resume_organization():
    # Attempt to process a test PDF (assumes a pdf exists or we create a dummy one)
    test_pdf_path = "test_resume.pdf"
    if not os.path.exists(test_pdf_path):
        with open(test_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n%EOF") # Minimal dummy PDF
    
    with open(test_pdf_path, "rb") as f:
        files = {"resume_file": (test_pdf_path, f, "application/pdf")}
        data = {"job_description": "Software Engineer with Python experience."}
        print(f"Sending request to {BACKEND_URL}/process_resume/...")
        try:
            resp = requests.post(f"{BACKEND_URL}/process_resume/", files=files, data=data)
            if resp.status_code == 200:
                result = resp.json()
                decision = result.get("decision", "Review")
                print(f"Success! Decision: {decision}")
                
                expected_path = os.path.join("resumes", decision.lower(), test_pdf_path)
                if os.path.exists(expected_path):
                    print(f"PASS: File found at {expected_path}")
                else:
                    print(f"FAIL: File NOT found at {expected_path}")
            else:
                print(f"Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Connection failed: {e}. Is the backend running?")

if __name__ == "__main__":
    test_resume_organization()
