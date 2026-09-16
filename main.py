from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path
from datetime import datetime
import os
import re
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="AI Resume Analyzer",
    description="AI-powered resume analysis and job matching system",
    version="1.0.0"
)


# =========================================================
# DIRECTORIES
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# =========================================================
# STATIC FILES
# =========================================================

if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static"
    )


# =========================================================
# HOME PAGE / LOGIN
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def home():

    login_file = STATIC_DIR / "login.html"

    if not login_file.exists():
        return """
        <html>
        <body style="font-family:Arial;text-align:center;padding:50px;">
            <h2>login.html not found</h2>
            <p>Please make sure login.html is inside the static folder.</p>
        </body>
        </html>
        """

    return login_file.read_text(encoding="utf-8")


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():

    index_file = STATIC_DIR / "index.html"

    if not index_file.exists():
        return """
        <html>
        <body style="font-family:Arial;text-align:center;padding:50px;">
            <h2>index.html not found</h2>
            <p>Please make sure index.html is inside the static folder.</p>
        </body>
        </html>
        """

    return index_file.read_text(encoding="utf-8")


# =========================================================
# RESUME TEXT EXTRACTION
# =========================================================

def extract_text(file_path, filename):

    text = ""

    try:

        # -----------------------------
        # PDF
        # -----------------------------

        if filename.lower().endswith(".pdf"):

            from pypdf import PdfReader

            reader = PdfReader(file_path)

            for page in reader.pages:

                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"

        # -----------------------------
        # DOCX
        # -----------------------------

        elif filename.lower().endswith(".docx"):

            from docx import Document

            document = Document(file_path)

            for paragraph in document.paragraphs:

                if paragraph.text.strip():
                    text += paragraph.text + "\n"

            # Also read tables inside DOCX
            for table in document.tables:

                for row in table.rows:

                    for cell in row.cells:

                        if cell.text.strip():
                            text += cell.text + "\n"

    except Exception as e:

        print("Text extraction error:", e)

    return text


# =========================================================
# SKILL LIST
# =========================================================

SKILLS = [

    "python",
    "java",
    "javascript",
    "typescript",

    "html",
    "css",

    "sql",
    "mysql",
    "postgresql",
    "mongodb",

    "fastapi",
    "django",
    "flask",

    "react",
    "node.js",

    "git",
    "github",
    "docker",

    "aws",
    "azure",

    "machine learning",
    "deep learning",
    "artificial intelligence",

    "data analysis",
    "pandas",
    "numpy",
    "scikit-learn",

    "tensorflow",
    "pytorch",

    "excel",
    "power bi",
    "tableau",

    "communication",
    "leadership",
    "problem solving",
    "teamwork"

]


# =========================================================
# SECTION LIST
# =========================================================

SECTIONS = {

    "summary": [
        "summary",
        "profile",
        "objective"
    ],

    "education": [
        "education",
        "academic"
    ],

    "experience": [
        "experience",
        "work experience",
        "employment"
    ],

    "skills": [
        "skills",
        "technical skills"
    ],

    "projects": [
        "projects",
        "project"
    ],

    "certifications": [
        "certifications",
        "certificates"
    ],

    "contact": [
        "email",
        "phone",
        "linkedin"
    ]

}


# =========================================================
# FIND SKILLS
# =========================================================

def find_skills(text):

    text_lower = text.lower()

    found = []

    for skill in SKILLS:

        # Escape special characters such as . in node.js
        pattern = r"(?<!\w)" + re.escape(skill.lower()) + r"(?!\w)"

        if re.search(pattern, text_lower):

            found.append(skill.title())

    return sorted(set(found))


# =========================================================
# FIND JOB SKILLS
# =========================================================

def find_job_skills(job_description):

    return find_skills(job_description)


# =========================================================
# FIND SECTIONS
# =========================================================

def find_sections(text):

    text_lower = text.lower()

    found = []
    missing = []

    for section, keywords in SECTIONS.items():

        exists = False

        for keyword in keywords:

            if keyword in text_lower:

                exists = True
                break

        if exists:

            found.append(section.title())

        else:

            missing.append(section.title())

    return found, missing


# =========================================================
# RESUME SCORE
# =========================================================

def calculate_resume_score(
    text,
    found_sections,
    missing_sections,
    skills
):

    score = 0

    text_lower = text.lower()

    # -----------------------------------------------------
    # CONTACT INFORMATION
    # -----------------------------------------------------

    if re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    ):
        score += 10

    if re.search(
        r"\b\d{10}\b",
        text_lower
    ):
        score += 10

    # -----------------------------------------------------
    # SECTIONS
    # -----------------------------------------------------

    score += min(
        len(found_sections) * 7,
        35
    )

    # -----------------------------------------------------
    # SKILLS
    # -----------------------------------------------------

    score += min(
        len(skills) * 3,
        20
    )

    # -----------------------------------------------------
    # RESUME LENGTH
    # -----------------------------------------------------

    word_count = len(text.split())

    if word_count >= 300:

        score += 10

    elif word_count >= 150:

        score += 5

    # -----------------------------------------------------
    # PROJECTS
    # -----------------------------------------------------

    if "project" in text_lower:

        score += 5

    # -----------------------------------------------------
    # CERTIFICATIONS
    # -----------------------------------------------------

    if (
        "certification" in text_lower
        or "certificate" in text_lower
    ):

        score += 5

    return min(score, 100)


# =========================================================
# ANALYZE RESUME
# =========================================================

@app.post("/analyze")
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...)
):

    temp_path = None

    try:

        # -------------------------------------------------
        # FILE NAME
        # -------------------------------------------------

        filename = file.filename or "resume"

        # -------------------------------------------------
        # FILE TYPE CHECK
        # -------------------------------------------------

        if not filename.lower().endswith(
            (".pdf", ".docx")
        ):

            return {
                "error":
                "Please upload a PDF or DOCX resume."
            }

        # -------------------------------------------------
        # CHECK FILE SIZE
        # -------------------------------------------------

        content = await file.read()

        if not content:

            return {
                "error":
                "The uploaded file is empty."
            }

        # -------------------------------------------------
        # SAVE TEMPORARY FILE
        # -------------------------------------------------

        suffix = Path(filename).suffix

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp:

            temp.write(content)

            temp_path = temp.name

        # -------------------------------------------------
        # EXTRACT RESUME TEXT
        # -------------------------------------------------

        resume_text = extract_text(
            temp_path,
            filename
        )

        # -------------------------------------------------
        # DELETE TEMP FILE
        # -------------------------------------------------

        try:

            if temp_path and os.path.exists(temp_path):

                os.remove(temp_path)

        except Exception:

            pass

        temp_path = None

        # -------------------------------------------------
        # EMPTY RESUME CHECK
        # -------------------------------------------------

        if not resume_text.strip():

            return {
                "error":
                "Could not read text from the resume. "
                "Please upload a text-based PDF or DOCX file."
            }

        # =================================================
        # SKILLS
        # =================================================

        resume_skills = find_skills(
            resume_text
        )

        job_skills = find_job_skills(
            job_description
        )

        # -------------------------------------------------
        # LOWERCASE SETS
        # -------------------------------------------------

        resume_skill_lower = {
            skill.lower()
            for skill in resume_skills
        }

        job_skill_lower = {
            skill.lower()
            for skill in job_skills
        }

        # -------------------------------------------------
        # MATCHING SKILLS
        # -------------------------------------------------

        matching = sorted(
            resume_skill_lower &
            job_skill_lower
        )

        # -------------------------------------------------
        # MISSING SKILLS
        # -------------------------------------------------

        missing = sorted(
            job_skill_lower -
            resume_skill_lower
        )

        matching_skills = [
            skill.title()
            for skill in matching
        ]

        missing_skills = [
            skill.title()
            for skill in missing
        ]

        # =================================================
        # JOB MATCH PERCENTAGE
        # =================================================

        if len(job_skill_lower) > 0:

            job_match = round(
                (
                    len(matching) /
                    len(job_skill_lower)
                ) * 100
            )

        else:

            job_match = 0

        # =================================================
        # SECTIONS
        # =================================================

        found_sections, missing_sections = find_sections(
            resume_text
        )

        # =================================================
        # RESUME SCORE
        # =================================================

        resume_score = calculate_resume_score(
            resume_text,
            found_sections,
            missing_sections,
            resume_skills
        )

        # =================================================
        # STRENGTHS
        # =================================================

        strengths = []

        if len(resume_skills) >= 5:

            strengths.append(
                "Good range of technical and professional skills."
            )

        if "Experience" in found_sections:

            strengths.append(
                "Work experience section is present."
            )

        if "Education" in found_sections:

            strengths.append(
                "Education section is included."
            )

        if "Projects" in found_sections:

            strengths.append(
                "Projects section is included."
            )

        if "Certifications" in found_sections:

            strengths.append(
                "Certifications section is included."
            )

        if not strengths:

            strengths.append(
                "Resume has a basic structure."
            )

        # =================================================
        # WEAKNESSES
        # =================================================

        weaknesses = []

        if missing_sections:

            weaknesses.append(
                "Some important resume sections are missing."
            )

        if missing_skills:

            weaknesses.append(
                "Some job-required skills are missing."
            )

        if not re.search(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            resume_text
        ):

            weaknesses.append(
                "Email address was not detected."
            )

        if not re.search(
            r"\b\d{10}\b",
            resume_text
        ):

            weaknesses.append(
                "Phone number was not detected."
            )

        if not weaknesses:

            weaknesses.append(
                "No major weaknesses were detected."
            )

        # =================================================
        # RECOMMENDATIONS
        # =================================================

        recommendations = []

        if "Contact" not in found_sections:

            recommendations.append(
                "Add your phone number and contact information."
            )

        if missing_skills:

            recommendations.append(
                "Add relevant missing skills if you have experience with them."
            )

        if "Projects" not in found_sections:

            recommendations.append(
                "Add a projects section with practical projects."
            )

        if "Certifications" not in found_sections:

            recommendations.append(
                "Add relevant certifications if available."
            )

        recommendations.append(
            "Keep your resume updated with your latest skills and experience."
        )

        # =================================================
        # IMPROVEMENTS
        # =================================================

        improvements = [

            "Use clear section headings.",

            "Keep formatting consistent.",

            "Use measurable achievements where possible.",

            "Tailor your resume to each job description.",

            "Keep the resume concise and easy to read."

        ]

        # =================================================
        # RETURN RESULT
        # =================================================

        return {

            "resume_score": resume_score,

            "job_match_percentage": job_match,

            "job_required_skills": job_skills,

            "matching_skills": matching_skills,

            "missing_skills": missing_skills,

            "found_sections": found_sections,

            "missing_sections": missing_sections,

            "strengths": strengths,

            "weaknesses": weaknesses,

            "recommendations": recommendations,

            "improvements": improvements

        }

    except Exception as e:

        print(
            "Analyze error:",
            str(e)
        )

        # Clean temporary file if error occurs

        try:

            if temp_path and os.path.exists(temp_path):

                os.remove(temp_path)

        except Exception:

            pass

        return {

            "error":
            "Unable to analyze resume. Please try again."

        }


# =========================================================
# PDF REPORT
# =========================================================

@app.post("/download-report")
async def download_report(

    resume_score: str = Form(...),

    job_match: str = Form(...),

    matching_skills: str = Form(""),

    missing_skills: str = Form(""),

    strengths: str = Form(""),

    weaknesses: str = Form(""),

    recommendations: str = Form("")

):

    try:

        # =================================================
        # REPORT FILE
        # =================================================

        report_file = BASE_DIR / "resume_analysis.pdf"

        # =================================================
        # DOCUMENT
        # =================================================

        document = SimpleDocTemplate(

            str(report_file),

            pagesize=A4,

            rightMargin=45,

            leftMargin=45,

            topMargin=45,

            bottomMargin=45

        )

        # =================================================
        # STYLES
        # =================================================

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(

            "CustomTitle",

            parent=styles["Title"],

            fontName="Helvetica-Bold",

            fontSize=24,

            leading=28,

            alignment=TA_CENTER,

            textColor=colors.HexColor("#1F2937"),

            spaceAfter=5

        )

        subtitle_style = ParagraphStyle(

            "Subtitle",

            parent=styles["BodyText"],

            fontName="Helvetica",

            fontSize=10,

            leading=14,

            alignment=TA_CENTER,

            textColor=colors.HexColor("#6B7280")

        )

        heading_style = ParagraphStyle(

            "CustomHeading",

            parent=styles["Heading2"],

            fontName="Helvetica-Bold",

            fontSize=14,

            leading=18,

            textColor=colors.HexColor("#1F2937"),

            spaceBefore=4,

            spaceAfter=8

        )

        normal_style = ParagraphStyle(

            "CustomBody",

            parent=styles["BodyText"],

            fontName="Helvetica",

            fontSize=10,

            leading=15,

            textColor=colors.HexColor("#374151")

        )

        footer_style = ParagraphStyle(

            "Footer",

            parent=styles["BodyText"],

            fontName="Helvetica",

            fontSize=8,

            alignment=TA_CENTER,

            textColor=colors.HexColor("#9CA3AF")

        )

        # =================================================
        # STORY
        # =================================================

        story = []

        # =================================================
        # TITLE
        # =================================================

        story.append(
            Spacer(1, 5)
        )

        story.append(
            Paragraph(
                "AI Resume Analyzer",
                title_style
            )
        )

        story.append(
            Paragraph(
                "Professional Resume Analysis Report",
                subtitle_style
            )
        )

        story.append(
            Spacer(1, 10)
        )

        # =================================================
        # HEADER LINE
        # =================================================

        header_line = Table(

            [[""]],

            colWidths=[500],

            rowHeights=[4]

        )

        header_line.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#2563EB")
                )

            ])

        )

        story.append(header_line)

        story.append(
            Spacer(1, 18)
        )

        # =================================================
        # DATE
        # =================================================

        date_text = datetime.now().strftime(
            "%d %B %Y, %I:%M %p"
        )

        date_table = Table(

            [

                [

                    Paragraph(
                        "<b>Analysis Date</b>",
                        normal_style
                    ),

                    Paragraph(
                        date_text,
                        normal_style
                    )

                ]

            ],

            colWidths=[
                120,
                380
            ]

        )

        date_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#F9FAFB")
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    colors.HexColor("#E5E7EB")
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    10
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    10
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                )

            ])

        )

        story.append(date_table)

        story.append(
            Spacer(1, 20)
        )

        # =================================================
        # SCORE CARDS
        # =================================================

        score_table = Table(

            [

                [

                    Paragraph(

                        "<b>RESUME SCORE</b><br/>"
                        f"<font size='24'><b>{resume_score}</b></font>"
                        "<font size='10'> / 100</font>",

                        normal_style

                    ),

                    Paragraph(

                        "<b>JOB MATCH</b><br/>"
                        f"<font size='24'><b>{job_match}%</b></font>",

                        normal_style

                    )

                ]

            ],

            colWidths=[
                250,
                250
            ],

            rowHeights=[
                75
            ]

        )

        score_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, 0),
                    colors.HexColor("#EFF6FF")
                ),

                (
                    "BACKGROUND",
                    (1, 0),
                    (1, 0),
                    colors.HexColor("#F0FDF4")
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.8,
                    colors.HexColor("#D1D5DB")
                ),

                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#E5E7EB")
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                )

            ])

        )

        story.append(score_table)

        story.append(
            Spacer(1, 25)
        )

        # =================================================
        # SECTION FUNCTION
        # =================================================

        def add_section(
            title,
            value,
            background
        ):

            story.append(
                Paragraph(
                    title,
                    heading_style
                )
            )

            if not value:

                value = "None found."

            items = value.split("|||")

            rows = []

            for item in items:

                item = item.strip()

                if item:

                    rows.append(

                        [

                            Paragraph(
                                "•",
                                normal_style
                            ),

                            Paragraph(
                                item,
                                normal_style
                            )

                        ]

                    )

            if not rows:

                rows = [

                    [

                        Paragraph(
                            "•",
                            normal_style
                        ),

                        Paragraph(
                            "None found.",
                            normal_style
                        )

                    ]

                ]

            section_table = Table(

                rows,

                colWidths=[
                    20,
                    480
                ]

            )

            section_table.setStyle(

                TableStyle([

                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        background
                    ),

                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#E5E7EB")
                    ),

                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP"
                    ),

                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),

                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        8
                    ),

                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        6
                    ),

                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        6
                    )

                ])

            )

            story.append(section_table)

            story.append(
                Spacer(1, 18)
            )

        # =================================================
        # REPORT SECTIONS
        # =================================================

        add_section(
            "Matching Skills",
            matching_skills,
            colors.HexColor("#F0FDF4")
        )

        add_section(
            "Missing Skills",
            missing_skills,
            colors.HexColor("#FFF7ED")
        )

        add_section(
            "Strengths",
            strengths,
            colors.HexColor("#F0FDF4")
        )

        add_section(
            "Weaknesses",
            weaknesses,
            colors.HexColor("#FEF2F2")
        )

        add_section(
            "Recommendations",
            recommendations,
            colors.HexColor("#EFF6FF")
        )

        # =================================================
        # IMPROVEMENT TIP
        # =================================================

        story.append(
            Spacer(1, 5)
        )

        tip_table = Table(

            [

                [

                    Paragraph(

                        "<b>Resume Improvement Tip</b><br/>"
                        "Regularly update your resume with new skills, "
                        "projects, certifications and measurable achievements.",

                        normal_style

                    )

                ]

            ],

            colWidths=[
                500
            ]

        )

        tip_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#F9FAFB")
                ),

                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.8,
                    colors.HexColor("#D1D5DB")
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    12
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    12
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    12
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    12
                )

            ])

        )

        story.append(tip_table)

        story.append(
            Spacer(1, 20)
        )

        # =================================================
        # FOOTER
        # =================================================

        story.append(

            Paragraph(
                "Generated by AI Resume Analyzer",
                footer_style
            )

        )

        # =================================================
        # PAGE NUMBER
        # =================================================

        def add_page_number(
            canvas,
            doc
        ):

            canvas.saveState()

            canvas.setFont(
                "Helvetica",
                8
            )

            canvas.setFillColor(
                colors.HexColor("#9CA3AF")
            )

            page_number = canvas.getPageNumber()

            canvas.drawString(
                45,
                25,
                "AI Resume Analyzer"
            )

            canvas.drawRightString(
                A4[0] - 45,
                25,
                f"Page {page_number}"
            )

            canvas.restoreState()

        # =================================================
        # BUILD PDF
        # =================================================

        document.build(

            story,

            onFirstPage=add_page_number,

            onLaterPages=add_page_number

        )

        # =================================================
        # RETURN PDF
        # =================================================

        return FileResponse(

            path=str(report_file),

            filename="resume_analysis.pdf",

            media_type="application/pdf"

        )

    except Exception as e:

        print(
            "PDF error:",
            str(e)
        )

        return {

            "error":
            "Unable to create PDF report."

        }


# =========================================================
# RUN SERVER
# =========================================================

@app.get("/logout")
def logout():
    return RedirectResponse(url="/")



if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        app,

        host="127.0.0.1",

        port=8000

    )