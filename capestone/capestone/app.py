from flask import Flask, render_template, request, redirect, url_for, flash
import boto3
import os
from botocore.config import Config

config = Config(signature_version='s3v4')

# Flask App Setup
app = Flask(__name__)
app.secret_key = 'secret_key_for_flask_session'

# AWS S3 Configuration
s3 = boto3.client(
    's3',
    aws_access_key_id='AKIAXKPUZUCMPHBZTDVX',
    aws_secret_access_key='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',
    region_name='ap-south-1',
    config=config
)
BUCKET_NAME = 'researchpaperstorage'


# Function to Search Papers in S3
def search_papers_in_s3(query):
    """Search papers in S3 by matching keywords in object metadata."""
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)
    matching_papers = []

    if 'Contents' in response:
        for obj in response['Contents']:
            # Retrieve object metadata
            head = s3.head_object(Bucket=BUCKET_NAME, Key=obj['Key'])
            metadata = head.get('Metadata', {})

            # Match query with metadata
            if any(query.lower() in str(metadata.get(field, '')).lower() for field in ['title', 'keywords', 'authors']):
                matching_papers.append({
                    'key': obj['Key'],
                    'title': metadata.get('title', 'Untitled'),
                    'authors': metadata.get('authors', 'Unknown'),
                    'year': metadata.get('year', 'N/A'),
                })
    return matching_papers


# Function to Upload Paper to S3
def upload_paper_to_s3(file, title, authors, keywords, year):
    """Uploads a paper to S3 with metadata."""
    s3.upload_fileobj(
        file,
        BUCKET_NAME,
        file.filename,
        ExtraArgs={
            'Metadata': {
                'title': title,
                'authors': authors,
                'keywords': keywords,
                'year': str(year),
            }
        }
    )


# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    papers = []
    if request.method == "POST":
        keywords = request.form.get("query")
        papers = search_papers_in_s3(keywords)
    return render_template("index.html", papers=papers)

def sanitize_metadata(value):
    """Sanitize metadata values by removing newline characters."""
    return value.replace("\n", " ").replace("\r", " ")

def upload_paper_to_s3(file, title, authors, keywords, year):
    """Uploads a paper to S3 with sanitized metadata."""
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

@app.route("/upload", methods=["GET", "POST"])
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
        return redirect(url_for('index'))

    return render_template("upload.html")


@app.route("/preview/<key>")
def preview_paper(key):
    """Generates a temporary preview link for the paper."""
    # Set the content type based on file extension (for example PDF)
    file_extension = os.path.splitext(key)[-1].lower()

    # Mapping file extensions to content types
    content_type_mapping = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain'
    }

    # Default to application/octet-stream if the file type is unknown
    content_type = content_type_mapping.get(file_extension, 'application/octet-stream')

    # Generate the presigned URL with content type
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': key, 'ResponseContentType': content_type},
        ExpiresIn=3600
    )
    print(f"Generated URL for preview: {url}")  # Debugging
    return redirect(url)

@app.route("/download/<key>")
def download_paper(key):
    """Generates a temporary download link for the paper."""
    url = s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME, 'Key': key}, ExpiresIn=3600)
    print(f"Generated URL for download: {url}")  # Debugging
    return redirect(url)

if __name__ == "__main__":
    app.run(debug=True)
