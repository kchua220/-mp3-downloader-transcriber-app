from flask import Flask, request, send_from_directory
import requests
from bs4 import BeautifulSoup
import os
import gc
from openai import OpenAI
from fpdf import FPDF
from celery import Celery

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
celery = Celery(app.name, broker=os.environ.get("REDIS_URL"))

# SCRAPE MP3 LINKS
def scrape_mp3_links(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    mp3_links = []
    for link in soup.find_all('a', href=True):
        if link['href'].endswith('.mp3'):
            full_link = requests.compat.urljoin(url, link['href'])
            display_name = link.get('title', '').strip() or "mp3"
            if display_name.endswith('.mp3'):
                display_name = display_name[:-4]
            mp3_links.append((full_link, display_name))
    return mp3_links

# CELERY TASK – DOWNLOAD, TRANSCRIBE, GENERATE PDF PER FILE
@celery.task
def process_mp3_task(mp3_url, display_name, folder_path):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    display_name = display_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    mp3_filename = display_name + ".mp3"
    pdf_filename = display_name + ".pdf"

    # Download MP3
    response = requests.get(mp3_url, stream=True)
    mp3_path = os.path.join(folder_path, mp3_filename)
    with open(mp3_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print(f"Downloaded {mp3_filename}")

    # Check size limit
    if os.path.getsize(mp3_path) > 25 * 1024 * 1024:
        print(f"Skipping {mp3_filename} - file too large for Whisper API (>{25}MB).")
        os.remove(mp3_path)
        return

    # Transcribe using OpenAI Whisper
    with open(mp3_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1"
        )
    transcript_text = transcript.text

    # Generate PDF
    pdf_path = os.path.join(folder_path, pdf_filename)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    font_path = os.path.join(os.path.dirname(__file__), 'static', 'fonts', 'NotoSansTC-Regular.ttf')
    pdf.add_font('NotoSansTC', '', font_path, uni=True)
    pdf.set_font('NotoSansTC', '', 12)

    for line in transcript_text.split('\n'):
        pdf.multi_cell(0, 10, line)
    pdf.output(pdf_path)
    print(f"Created transcript PDF: {pdf_filename}")

    # Clean up
    os.remove(mp3_path)
    print(f"Deleted {mp3_filename} to free space")
    gc.collect()

# ROUTES
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form["url"]
        folder_name = request.form["folder"]

        mp3_links = scrape_mp3_links(url)
        if not mp3_links:
            return "No MP3 links found."

        # Create folder to save files in static directory
        folder_path = os.path.join("static", folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # Enqueue each MP3 for background processing
        for mp3_url, display_name in mp3_links:
            process_mp3_task.delay(mp3_url, display_name, folder_path)

        # Inform user tasks are running
        return f"""
            <h2>Processing Started</h2>
            <p>Your files are being transcribed in the background. Refresh this page later to download completed PDFs.</p>
            <a href="/">Back</a>
        """

    return '''
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; margin: 50px; }
            h1 { font-size: 32px; }
            input[type="text"] {
                width: 400px;
                height: 40px;
                font-size: 16px;
                padding: 5px 10px;
                margin-bottom: 20px;
            }
            input[type="submit"] {
                font-size: 18px;
                padding: 10px 20px;
            }
        </style>
    </head>
    <body>
        <form method="post">
            Enter URL <br>
            <input type="text" name="url" required><br><br>
            Enter Folder Name <br>
            <input type="text" name="folder" required><br><br>
            <input type="submit" value="Download & Transcribe">
        </form>
    </body>
    </html>
'''

# DOWNLOAD ROUTE
@app.route("/download/<folder>/<filename>")
def download(folder, filename):
    folder_path = os.path.join("static", folder)
    return send_from_directory(folder_path, filename, as_attachment=True)

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(debug=True)