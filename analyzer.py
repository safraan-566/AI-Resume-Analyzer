import re


def analyze_resume(text):
    email = re.findall(r'\S+@\S+', text)

    phone = re.findall(r'\b\d{10}\b', text)

    skills = []

    skill_list = [
        "Python",
        "FastAPI",
        "Java",
        "SQL",
        "HTML",
        "CSS",
        "JavaScript",
        "Machine Learning",
        "Data Science"
    ]

    for skill in skill_list:
        if skill.lower() in text.lower():
            skills.append(skill)

    return {
        "email": email,
        "phone": phone,
        "skills": skills
    }