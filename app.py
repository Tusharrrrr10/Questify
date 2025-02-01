import os
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import pdfplumber
import docx
import google.generativeai as genai
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
import easyocr



# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your_secret_key'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

# Google Generative AI setup
os.environ["GOOGLE_API_KEY"] = "your api key"  # Replace with your API key
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("models/gemini-1.5-pro")


# Helper: Check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Helper: Extract text from files
reader = easyocr.Reader(['en'])

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    try:
        if ext == 'pdf':
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
                    else:
                        # Use EasyOCR for non-textual pages
                        image = page.to_image(resolution=300).original.convert("RGB")
                        image_path = file_path + ".png"  # Temporarily save image
                        image.save(image_path)
                        ocr_text = reader.readtext(image_path, detail=0)
                        text += "\n".join(ocr_text)
                        os.remove(image_path)  # Clean up temporary image
            return text.strip()
        elif ext == 'docx':
            doc = docx.Document(file_path)
            return '\n'.join(paragraph.text for paragraph in doc.paragraphs if paragraph.text)
        elif ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            return None
    except Exception as e:
        raise ValueError(f"Error extracting text: {str(e)}")



# Detect text language
def detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        return "en"  # Default to English if detection fails


# Generate content based on the detected language
def generate_content(prompt, language):
    if language != "en":
        prompt = f"Respond in {language}: {prompt}"
    response = model.generate_content(prompt).text.strip()
    return response


# Generate MCQs
def generate_mcqs(input_text, num_questions, language):
    prompt = f"""
    Generate {num_questions} MCQs based on the following text:
    '{input_text}'
    Each question should have four options and new line for each option.
    Format:
    Question [question]
    Options [options]
    Correct Answer [correct answer]
    """
    return generate_content(prompt, language)


# Generate QA pairs
def generate_qa_pairs(input_text, num_questions, language):
    prompt = f"""
    Generate {num_questions} question-answer pairs based on the following text:
    '{input_text}'
    Format:
    **Question: [question]
    **Answer: [answer]
    """
    return generate_content(prompt, language)


# Generate Fill-in-the-Blanks
def generate_fill_in_the_blanks(input_text, num_questions, language):
    prompt = f"""
    Generate {num_questions} fill-in-the-blank questions based on the following text:
    '{input_text}'
    Replace key terms with blanks (____) and provide the correct term as the answer.
    """
    return generate_content(prompt, language)


# Generate True/False Questions
def generate_true_false_questions(input_text, num_questions, language):
    prompt = f"""
    Generate {num_questions} True/False questions based on the following text:
    '{input_text}'
    Clearly state whether the answer is True or False.
    Format:
    Question [question]
    Answer [answer]
    Explanation
    """
    return generate_content(prompt, language)


# Generate Summary
def generate_summary(input_text, num_sentences, language):
    prompt = f"""
    Summarize the following text in {num_sentences} sentences:
    '{input_text}'
    """
    return generate_content(prompt, language)

# Generate Question Paper
def generate_question_paper(input_text, num_questions, language):
    prompt = f"""
    Create a comprehensive question paper based on the following text:
    '{input_text}'
    Include the following:
    1. {num_questions}  multiple-choice questions.
    2. {num_questions}  True/False questions.
    3. {num_questions}  fill-in-the-blank questions.
    4. {num_questions}  qustion answer
    Each question should have clear formatting and do not include answers just question and do not show marks.
    """
    return generate_content(prompt, language)

# Generate Question Paper with solution
def generate_question_paper_solution(input_text, num_questions, language):
    prompt = f"""
    Create a comprehensive question paper based on the following text:
    '{input_text}'
    Include the following:
    1. {num_questions}  multiple-choice questions.
    2. {num_questions}  True/False questions.
    3. {num_questions}  fill-in-the-blank questions.
    4. {num_questions}  qustion answer
    Each question should have clear formatting and include answers after each question and do not show marks.
    """
    return generate_content(prompt, language)


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')





@app.route('/generate', methods=['POST'])
def generate_questions():
    try:
        # Retrieve form inputs
        generator_type = request.form.get('generator_type')
        num_questions = int(request.form.get('num_questions', 5))
        num_sentences = int(request.form.get('num_sentences', 3))  # For summaries

        if 'file' not in request.files or not request.files['file']:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if not allowed_file(file.filename):
            return jsonify({"error": "Unsupported file type"}), 400

        # Save and process file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)

        text = extract_text_from_file(filepath)
        language = detect_language(text)

        # Generate content based on type
        if generator_type == 'mcq':
            result = generate_mcqs(text, num_questions, language)
            display_type = "MCQs"
        elif generator_type == 'qa':
            result = generate_qa_pairs(text, num_questions, language)
            display_type = "Question-Answer Pairs"
        elif generator_type == 'fill_blank':
            result = generate_fill_in_the_blanks(text, num_questions, language)
            display_type = "Fill-in-the-Blanks"
        elif generator_type == 'true_false':
            result = generate_true_false_questions(text, num_questions, language)
            display_type = "True/False Questions"
        elif generator_type == 'summary':
            result = generate_summary(text, num_sentences, language)
            display_type = "Text Summary"
        elif generator_type == 'question_paper':
            result = generate_question_paper(text, num_questions, language)
            display_type = "Question Paper"
        elif generator_type == 'question_paper_solution':
            result = generate_question_paper_solution(text, num_questions, language)
            display_type = "Question Paper with Answers"
        else:
            return jsonify({"error": "Invalid generator type"}), 400

        os.remove(filepath)  # Cleanup uploaded file

        # Save results to file for download
        downloads_dir = 'downloads'
        os.makedirs(downloads_dir, exist_ok=True)
        output_filename = f"{generator_type}_results.txt"
        output_filepath = os.path.join(downloads_dir, output_filename)
        with open(output_filepath, 'w', encoding='utf-8') as output_file:
            output_file.write(result)

        # Render results
        return render_template(
            'results.html',
            result=result,
            display_type=display_type,
            download_link=f"/downloads/{output_filename}"
        )
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


# Route to serve downloads
@app.route('/downloads/<filename>')
def download_file(filename):
    try:
        return send_from_directory('downloads', filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404



@app.errorhandler(404)
def page_not_found(e):
    return render_template('about.html'), 404


if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)



