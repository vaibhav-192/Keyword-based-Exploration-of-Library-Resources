from flask import Flask, render_template, request, redirect, url_for, flash
import boto3
import os
from botocore.config import Config
from langchain_openai import OpenAI
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain.chains import SequentialChain
from flask import jsonify

OpenAI.api_key = ''
# Initialize the LLM globally
llm = OpenAI(temperature=0.1)


config = Config(signature_version='s3v4')

# Flask App Setup
app = Flask(__name__)
app.secret_key = 'secret_key_for_flask_session'

# AWS S3 Configuration
s3 = boto3.client(
    's3',
    aws_access_key_id='',
    aws_secret_access_key='',
    region_name='ap-south-1',
    config=config
)
BUCKET_NAME = 's3researchpapers'

def Transalate(Search_Text):
    answer = []
    try:
        # Prompt to determine the language of the input text
        prompt1 = PromptTemplate(
            input_variables=["Search_Text"], 
            template="Identify only the name of the language of the text: {Search_Text}."
        )
        chain1 = LLMChain(llm=llm, prompt=prompt1, verbose=False, output_key='language')
        
        prompt2 = PromptTemplate(
            input_variables=["Search_Text"], 
            template="Transliterate the {Search_Text} into English."
        )
        chain2 = LLMChain(llm=llm, prompt=prompt2, verbose=False, output_key='transliterated_text')
        
        # Prompt to translate the input text to English
        prompt3 = PromptTemplate(
            input_variables=["Search_Text", "language"], 
            template="Translate the {Search_Text} into English."
        )
        chain3 = LLMChain(llm=llm, prompt=prompt3, verbose=False, output_key='Translated_Text')

        # Combine both chains sequentially
        final_chain = SequentialChain(
            chains=[chain1, chain2, chain3],
            input_variables=["Search_Text"], 
            output_variables=['Search_Text','language', 'Translated_Text', 'transliterated_text'],
            verbose=False
        )

        # Run the chain with the provided input
        response = final_chain({"Search_Text": Search_Text})
        
        # Strip leading and trailing whitespaces
        answer.append(response['Translated_Text'].strip())
        answer.append(response['transliterated_text'].strip())
        answer.append(response['Search_Text'].strip())
        
        return answer

    except Exception as e:
        print(f"An error occurred: {e}")


# Function to Search Papers in S3
def search_papers_in_s3(queries):
    """Search papers in S3 by matching keywords in object metadata."""
    print(f"Search Queries: {queries}")  # Debugging line to check queries
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)
    matching_papers = []
    if 'Contents' in response:
        for obj in response['Contents']:
            # Retrieve object metadata
            head = s3.head_object(Bucket=BUCKET_NAME, Key=obj['Key'])
            metadata = head.get('Metadata', {})
            print(f"Metadata for {obj['Key']}: {metadata}")  # Debugging line to check metadata
            
            for query in queries:
                if any(query.lower() in str(metadata.get(field, '')).lower() for field in ['title', 'keywords', 'authors']):
                    matching_papers.append({
                        'key': obj['Key'],
                        'title': metadata.get('title', 'Untitled'),
                        'authors': metadata.get('authors', 'Unknown'),
                        'year': metadata.get('year', 'N/A'),
                    })
    return matching_papers

def sanitize_metadata(value):
    """Sanitize metadata values by removing newline characters."""
    return value.replace("\n", " ").replace("\r", " ")

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

@app.route("/", methods=["GET", "POST"])
def index():
    papers = []
    filtered_papers = []
    selected_year = None

    if request.method == "POST":
        keywords = request.form.get("query")
        translate_output = Transalate(keywords)
        papers = search_papers_in_s3(translate_output)

        # Filter by year if selected
        selected_year = request.form.get("year")
        if selected_year:
            filtered_papers = [paper for paper in papers if paper['year'] == selected_year]
        else:
            filtered_papers = papers
    else:
        filtered_papers = papers

    return render_template("index.html", papers=filtered_papers, all_papers=papers, selected_year=selected_year)

KEYWORDS = [
    "Artificial Intelligence", "Artificial Neural Networks", "Deep Learning", 
    "Machine Learning", "Reinforcement Learning", "Computer Vision", 
    "Natural Language Processing", "AI Ethics", "Data Science", 
    "Robotics", "Big Data", "Algorithm Design", "Supervised Learning", 
    "Unsupervised Learning", "Generative Adversarial Networks", "Cloud Computing",
    "Edge Computing", "Quantum Computing", "Blockchain", "Cybersecurity", 
    "Cryptography", "Big Data Analytics", "Data Mining", "Cloud Security",
    "Internet of Things (IoT)", "5G Technology", "Augmented Reality", "Virtual Reality",
    "Autonomous Systems", "Natural Language Generation", "Speech Recognition", 
    "Recommender Systems", "Human-Computer Interaction", "Digital Twins", 
    "Computer Networks", "Database Management", "Distributed Systems", 
    "Parallel Computing", "Computational Neuroscience", "Smart Cities", "Bioinformatics",
    "Privacy Preserving Computation", "AI in Healthcare", "Robotic Process Automation",
    "Graph Theory", "Data Structures", "Computational Complexity", "Computational Biology",
    "Cloud Infrastructure", "Software Engineering", "Mobile App Development", "Agile Development",
    "DevOps", "Web Development", "Machine Vision", "Neural Machine Translation", "Fuzzy Logic",
    "Optimization Algorithms", "AI in Education", "Edge AI", "AI for Social Good", 
    "Autonomous Vehicles", "Swarm Robotics", "Game Theory", "Digital Signal Processing",
    "Pattern Recognition", "Reinforcement Learning in Games", "AI and Ethics", 
    "Smart Homes", "Wearable Technology", "Data Visualization", "Knowledge Graphs",
    "AI for Finance", "Deep Reinforcement Learning", "AI in Manufacturing", "AI in Retail", 
    "Deepfake Technology", "Facial Recognition", "Augmented Intelligence", "Biometric Security"
]

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    query = request.args.get("q", "").lower()
    suggestions = [kw for kw in KEYWORDS if query in kw.lower()]
    return jsonify(suggestions[:10])  # Return top 10 suggestions


if __name__ == "__main__":
    app.run(debug=True)