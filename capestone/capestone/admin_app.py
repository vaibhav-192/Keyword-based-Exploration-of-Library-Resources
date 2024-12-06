from flask import Flask, render_template, request, redirect, url_for, flash
import boto3
from botocore.config import Config

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
BUCKET_NAME = 'researchpaperstorage'

# Sanitize metadata
def sanitize_metadata(value):
    return value.replace("\n", " ").replace("\r", " ")

# Upload Functionality
def upload_paper_to_s3(file, title, authors, keywords, year):
    sanitized_title = sanitize_metadata(title)
    sanitized_authors = sanitize_metadata(authors)
    sanitized_keywords = sanitize_metadata(keywords)
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
        title = request.form['title']
        authors = request.form['authors']
        year = request.form['year']
        keywords = request.form['keywords']
        file = request.files['file']

        # Upload file to S3
        upload_paper_to_s3(file, title, authors, keywords, year)

        flash('Paper uploaded successfully!', 'success')
        return redirect(url_for('upload_paper'))

    return render_template("upload_admin.html")

if __name__ == "__main__":
    app.run(port=5001, debug=True)
