from flask import Flask, render_template, request, redirect, url_for, flash
import boto3
from botocore.config import Config
import fitz  # PyMuPDF for font size detection
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string
import os

nltk.download('punkt')
nltk.download('stopwords')

# Flask App Setup
app = Flask(__name__)
app.secret_key = 'admin_secret_key'

# AWS S3 Configuration
s3 = boto3.client(
    's3',
    aws_access_key_id='',
    aws_secret_access_key='',
    region_name='ap-south-1',
    config=Config(signature_version='s3v4')
)
BUCKET_NAME = 's3researchpapers'

# Sanitize metadata
def sanitize_metadata(value):
    return value.replace("\n", " ").replace("\r", " ")

# Extract Text from PDF
def extract_text_from_pdf(file):
    text = ""
    pdf_document = fitz.open(stream=file.read(), filetype="pdf")
    for page in pdf_document:
        text += page.get_text()
    file.seek(0)  # Reset file pointer
    return text, pdf_document

# Extract Title from PDF using font size
def extract_title_from_pdf(pdf_document):
    title = ""
    font_sizes = []

    # Collect all text with font sizes from the first few pages
    for page_num, page in enumerate(pdf_document):
        if page_num > 2:  # Limit to first 3 pages for title detection
            break
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        font_sizes.append((span["size"], span["text"]))

    # Sort text by font size (descending) and extract the largest font text
    if font_sizes:
        font_sizes.sort(key=lambda x: x[0], reverse=True)
        title_candidates = [text.strip() for size, text in font_sizes if len(text.strip()) > 3]
        if title_candidates:
            title = title_candidates[0]  # Pick the text with the largest font size

    return title.strip()

# Improved Metadata Extraction: Authors, Year
def extract_metadata_from_text(text):
    authors, year = "", ""

    # Extract Year - look for 4-digit numbers from 1900 to 2099
    year_candidates = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    if year_candidates:
        year = year_candidates[0]  # Picks the first valid year

    # Extract Authors - look for lines starting with 'By' or 'Authors'
    author_patterns = [
        r"(?i)^\s*(?:by|authors?)\s*[:\-]?\s*(.*)",  # Matches "By John Doe" or "Authors: Jane Smith"
    ]
    for line in text.split("\n"):
        for pattern in author_patterns:
            match = re.match(pattern, line.strip())
            if match:
                authors = match.group(1).strip()
                break
        if authors:
            break

    # Sanitize extracted values
    authors = authors if authors else "Unknown Authors"
    year = year if year else "Unknown Year"

    return authors, year

# Extract Keywords from Text
def extract_keywords(text, num_keywords=10):
    stop_words = set(stopwords.words('english'))
    words = word_tokenize(text)

    # Filter words: remove stopwords, punctuation, and numbers
    filtered_words = [
        word.lower() for word in words
        if word.lower() not in stop_words and word.isalpha() and word not in string.punctuation
    ]

    # Count word frequency
    word_freq = {}
    for word in filtered_words:
        word_freq[word] = word_freq.get(word, 0) + 1

    # Sort words by frequency and return top N
    sorted_keywords = sorted(word_freq, key=word_freq.get, reverse=True)
    return sorted_keywords[:num_keywords]

# Upload Functionality
def upload_paper_to_s3(file, title, authors, keywords, year):
    sanitized_title = sanitize_metadata(title)
    sanitized_authors = sanitize_metadata(authors)
    sanitized_keywords = sanitize_metadata(", ".join(keywords))
    sanitized_year = sanitize_metadata(str(year))

    s3.upload_fileobj(
        file,
        BUCKET_NAME,
        file.filename,
        ExtraArgs={
            'Metadata': {
                'title': sanitized_title,
                'authors': sanitized_authors,
                'keywords': sanitized_keywords,
                'year': sanitized_year,
            }
        }
    )

@app.route("/", methods=["GET", "POST"])
def upload_paper():
    if request.method == "POST":
        file = request.files['file']

        if file and file.filename.endswith('.pdf'):
            try:
                # Extract text and PDF document
                text, pdf_document = extract_text_from_pdf(file)
                file.seek(0)  # Reset file pointer for S3 upload

                # Extract title using font size
                title = extract_title_from_pdf(pdf_document)

                # Extract authors and year from text
                authors, year = extract_metadata_from_text(text)
                keywords = extract_keywords(text)

                # Use default values if extraction fails
                title = title if title else "Unknown Title"
                authors = authors if authors else "Unknown Authors"
                year = year if year else "Unknown Year"

                # Upload file to S3
                upload_paper_to_s3(file, title, authors, keywords, year)

                flash('Paper uploaded successfully!', 'success')
                return redirect(url_for('upload_paper'))
            except Exception as e:
                flash(f'Error processing the file: {str(e)}', 'danger')
        else:
            flash('Please upload a valid PDF file.', 'danger')

    return render_template("upload_admin.html")

if __name__ == "__main__":
    app.run(port=5001, debug=True)
