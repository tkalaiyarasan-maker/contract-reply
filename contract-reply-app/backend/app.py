from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
import re
import tempfile
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")

UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {"pdf", "docx"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_file(filepath):
    if filepath.endswith(".pdf"):
        text = ""
        reader = PdfReader(filepath)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    elif filepath.endswith(".docx"):
        doc = Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    return ""


def extract_references(text):
    refs = re.findall(r"[A-Z]{2,}\/.*?\d{4}.*?\d{2,4}", text)
    dates = re.findall(r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}", text)
    return {"refs": list(dict.fromkeys(refs)), "dates": list(dict.fromkeys(dates))}


@app.route("/api/generate-draft", methods=["POST"])
def generate_draft():
    file = request.files.get("file")
    reply_input = request.form.get("replyInput")

    if not file or not allowed_file(file.filename):
        return jsonify({"error": "Invalid or missing file"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    text = extract_text_from_file(filepath)
    refs = extract_references(text)

    prompt = f"""You are a contract administrator drafting a formal reply letter.
    The uploaded letter includes these references: {refs['refs']}
    and dates: {refs['dates']}.
    Prepare a professional, formatted reply letter addressing:
    {reply_input}."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in drafting contractual correspondence."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        draft = response.choices[0].message["content"]
        return jsonify({"draft": draft, "references": refs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/redraft", methods=["POST"])
def redraft():
    data = request.get_json()
    draft = data.get("draft")
    suggestion = data.get("suggestion")

    prompt = f"""Revise the following contractual letter based on these suggestions:
    {suggestion}
    Letter:
    {draft}"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional letter editor."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        redrafted = response.choices[0].message["content"]
        return jsonify({"redrafted": redrafted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
