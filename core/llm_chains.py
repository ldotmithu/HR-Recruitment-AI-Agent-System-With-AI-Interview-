import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import GoogleGenerativeAI


try:
    llm = ChatGroq(model="openai/gpt-oss-20b",temperature=0.2)
    #llm = GoogleGenerativeAI(model="gemini-1.5-pro")
    print(" LLM initialized successfully")
except Exception as e:
    raise e 

if llm:
    resume_summarizer_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an HR assistant. Summarize the following resume for a quick review, highlighting key skills and experience relevant to the job description."),
        ("user", "Resume:\n{resume_text}\n\nJob Description:\n{job_text}")
    ])
    resume_summarizer = resume_summarizer_prompt | llm | StrOutputParser()

    # Interview Chain
    interview_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an experienced and professional HR interviewer. Your goal is to conduct a mock interview with a candidate based on their resume and the job description.
        
        Guidelines:
        1.  The interview sequence is strictly 5 questions in total.
        2.  Question 1: Always ask the candidate to introduce themselves and highlight their relevant experience.
        3.  Questions 2-5: Ask relevant technical or behavioral questions based on the candidate's resume and the job requirements.
        4.  Ask ONE question at a time. Evaluate the candidate's previous response briefly before asking the next question.
        5.  Do NOT ask for feedback or end the interview yourself; the system will handle the transition after 5 responses.
        6.  Keep the tone professional, encouraging, and focused.
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_text}
        
        Chat History:
        {chat_history}
        """),
        ("user", "{user_input}")
    ])
    interview_chain = interview_prompt | llm | StrOutputParser()

    # Feedback Chain
    feedback_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert HR evaluator. You have just conducted a mock interview with a candidate.
        Based on the transcript below, provide a constructive performance review.
        
        Include:
        1. Strengths: What did the candidate do well?
        2. Areas for Improvement: What could be better?
        3. Overall Rating: (1-10)
        4. Final Recommendation: (Hire / Strong Hire / Weak Hire / Reject)
        
        Be professional, encouraging, and specific.
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_text}
        
        Interview Transcript:
        {chat_history}
        """),
        ("user", "Please generate the feedback now.")
    ])
    feedback_chain = feedback_prompt | llm | StrOutputParser()

else:
    resume_summarizer = None
    interview_chain = None
    feedback_chain = None