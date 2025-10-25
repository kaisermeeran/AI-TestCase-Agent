import streamlit as st
import pandas as pd
import requests
import io
import re
import pdfplumber
from dotenv import load_dotenv
import os
from docx import Document
import configparser
import streamlit as st
import configparser
import os

# ===============================
# 🔑 Configure API Key
# ===============================
OPENROUTER_API_KEY = st.secrets["openrouter"]["api_key"]
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ===============================
# 🧠 AI Test Case Generator
# ===============================
def generate_testcase(description, extra_instruction=""):
    prompt = f"""
    You are a QA Test Case Generator.
    Based on this requirement, create:
    - Pre-requisite (if any)
    - Test Case Title
    - Test Steps
    - Expected Result (in a separate section)

    Requirement: {description}

    {"Additional Instruction: " + extra_instruction if extra_instruction else ""}
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 400
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    data = response.json()

    try:
        text = data["choices"][0]["message"]["content"]

        pre_req_match = re.search(
            r"(Pre-?requisite\s*:?-?\s*)([\s\S]*?)(?=(Test Case Title|Test Steps|Expected Result|$))",
            text, re.IGNORECASE
        )
        expected_match = re.search(
            r"(Expected\s*Result\s*:?-?\s*)([\s\S]*)", text, re.IGNORECASE
        )

        pre_requisite = pre_req_match.group(2).strip() if pre_req_match else ""
        expected_result = expected_match.group(2).strip() if expected_match else "Not specified"

        cleaned_text = text
        if pre_req_match:
            cleaned_text = cleaned_text.replace(pre_req_match.group(0), "")
        if expected_match:
            cleaned_text = cleaned_text.replace(expected_match.group(0), "")

        cleaned_text = re.sub(r"\n{2,}", "\n", cleaned_text.strip())
        return pre_requisite, cleaned_text, expected_result

    except Exception as e:
        return "", f"Error generating test case: {str(e)}", ""

# ===============================
# 📄 File Reader Functions
# ===============================
def extract_requirements_from_docx(file):
    doc = Document(file)
    requirements = []
    capture = False
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if re.search(r"\brequirements\b", text, re.IGNORECASE):
            capture = True
            continue
        if capture and re.match(r"^[A-Z\s]{3,}$", text):
            capture = False
            continue
        if capture and (text.startswith(("•", "-", "*")) or re.search(r"\b(must|should|shall)\b", text, re.IGNORECASE)):
            text = re.sub(r"^[•\-\*]\s*", "", text)
            requirements.append(text)
    return requirements



# ===============================
# 🌐 Streamlit UI
# ===============================
st.set_page_config(page_title="AI Test Case Generator Agent", page_icon="🤖", layout="centered")
st.title(" Unique Force Technology Solution and Pvt Ltd")

st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(to right, #f57824, white);
            color: black;
        }
        h1 {
            text-align: center;
            color: #00897b;
            font-weight: bold;
        }
        .stButton>button {
            background-color: #00bfa5;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            padding: 0.6em 1.2em;
        }
        .stButton>button:hover {
            background-color: #1de9b6;
            color: black;
        }
        .custom-success {
            background-color: rgba(0,255,0,0.1);
            padding: 10px;
            border-radius: 8px;
            color: black;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 AI Test Case Generator Agent")


uploaded_file = st.file_uploader("📂 Upload Excel, Word, or PDF file", type=["xlsx", "docx", "pdf"])
user_instruction = st.text_area("🧠 Enter special instructions (optional):", placeholder="e.g., Expected Result text color should be in Green color")
generate_multiple = st.checkbox("Generate multiple test cases per requirement", value=False)

# Initialize session memory
if "results" not in st.session_state:
    st.session_state["results"] = []

# ===============================
# 🚀 Generate Test Cases
# ===============================
if uploaded_file and st.button("🚀 Generate Test Cases"):
    # Reset previous results
    st.session_state["results"] = []

    # Read file and extract requirements
    requirements = []
    file_name = uploaded_file.name.lower()
    
    if file_name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
        if "Requirement" in df.columns:
            requirements = df["Requirement"].dropna().tolist()
        else:
            st.error("❌ Excel must contain a 'Requirement' column.")
            st.stop()
    elif file_name.endswith(".docx"):
        requirements = extract_requirements_from_docx(uploaded_file)
    elif file_name.endswith(".pdf"):
        requirements = extract_requirements_from_pdf(uploaded_file)
    else:
        st.error("❌ Unsupported file format.")
        st.stop()

    if not requirements:
        st.warning("⚠️ No valid requirements found in file.")
        st.stop()

    # Generate test cases
    new_results = []
    for i, req in enumerate(requirements, start=1):
        ts_id = f"TC_{i}"
        pre_req, testcase, expected = generate_testcase(req, user_instruction)
        new_results.append({
            "TS_ID": ts_id,
            "Requirement": req,
            "Pre-requisite": pre_req,
            "Generated_TestCase": testcase,
            "Expected_Result": expected
        })

    # Store in session
    st.session_state["results"].extend(new_results)

    # Display results
    st.dataframe(pd.DataFrame(st.session_state["results"]))

    # Output to Excel
    output = io.BytesIO()
    pd.DataFrame(st.session_state["results"]).to_excel(output, index=False)
    output.seek(0)

    st.balloons()
    st.download_button(
        label="⬇️ Download All Generated Test Cases",
        data=output,
        file_name="Generated_TestCases.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


from flask import Flask, request, jsonify
import threading

# Create Flask app
app = Flask(__name__)

@app.route('/api/generate_testcases', methods=['POST'])
def api_generate_testcases():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    # Extract list of requirements
    requirements_list = data.get("requirements", [])
    if not requirements_list:
        return jsonify({"error": "Missing 'requirements' list"}), 400

    results = []

    # Loop through each requirement and generate test case
    for item in requirements_list:
        req_text = item.get("text")
        extra_inst = item.get("extra_instruction", "")
        pre_req, testcase, expected = generate_testcase(req_text, extra_inst)
        results.append({
            "requirement": req_text,
            "pre_requisite": pre_req,
            "test_case": testcase,
            "expected_result": expected
        })

    return jsonify(results)

# Run Flask server in a separate thread
def run_flask():
    app.run(port=8000, debug=False, use_reloader=False)

threading.Thread(target=run_flask).start()



