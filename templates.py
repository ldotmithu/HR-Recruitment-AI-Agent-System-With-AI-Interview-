import os

folders = [
    "agents",
    "workflows",
    "schemas",
    "api",
    "ui",
]

files = {
    "agents/__init__.py": "",
    "agents/resume_extractor.py": "# Extract text + email from resume\n",
    "agents/ats_scorer.py": "# GPT-4 based ATS scoring\n",
    "agents/email_sender.py": "# Sends rejection email\n",

    "workflows/__init__.py": "",
    "workflows/langgraph_workflow.py": "# LangGraph flow with LLM and conditional logic\n",

    "schemas/__init__.py": "",
    "schemas/state_schema.py": "# TypedDict for shared LangGraph state\n",

    "api/__init__.py": "",
    "api/main.py": "# FastAPI endpoint to receive resumes\n",

    "ui/__init__.py": "",
    "ui/streamlit_app.py": "# Streamlit UI for resume upload and feedback\n",

    ".env": (
        "# Put your sensitive config here\n"
        "EMAIL_SENDER=your_email@gmail.com\n"
        "EMAIL_PASSWORD=your_app_password\n"
        "OPENAI_API_KEY=your_openai_key\n"
    ),

    "requirements.txt": (
        "# Python dependencies\n"
        "fastapi\n"
        "uvicorn\n"
        "langgraph\n"
        "langchain\n"
        "langchain-openai\n"
        "PyPDF2\n"
        "sentence-transformers\n"
        "smtplib\n"
        "python-dotenv\n"
        "streamlit\n"
        "requests\n"
    ),

    "README.md": "# HR Recruitment AI Agent System\n"
}

def create_structure():
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
    for filepath, content in files.items():
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    print("✅ Project structure and .py files created successfully.")

if __name__ == "__main__":
    create_structure()
