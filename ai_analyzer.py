from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def analyze_with_ai(resume_text, job_description):

    prompt = f"""
Analyze this resume for this job.

Resume:
{resume_text}

Job Description:
{job_description}

Give:
- Strengths
- Weaknesses
- Missing skills
- Improvements
- Interview tips
"""

    response = client.responses.create(
        model="gpt-5.6",
        input=prompt
    )

    return response.output_text