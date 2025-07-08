from flask import Flask, request, send_from_directory
import requests
from bs4 import BeautifulSoup
import os
from openai import OpenAI
from fpdf import FPDF

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

# DOWNLOAD, TRANSCRIBE, GENERATE PDF
def process_mp3s(mp3_links, folder_path):
    for mp3_url, display_name in mp3_links:
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

        # Process MP3s (download + transcribe + pdf)
        process_mp3s(mp3_links, folder_path)

        # Display links to downloaded files for user
        files = os.listdir(folder_path)
        file_links = [f"<li><a href='/download/{folder_name}/{file}'>{file}</a></li>" for file in files]
        return f"""
            <h2>Download Completed Files</h2>
            <ul>{''.join(file_links)}</ul>
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