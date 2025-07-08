from openai import OpenAI
from fpdf import FPDF

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Transcribe the audio file
with open("/Users/kevinc220/Downloads/02議事規則擬訂作業及健保新藥核價作業說明.mp3", "rb") as audio_file:
    transcript = client.audio.transcriptions.create(
        file=audio_file,
        model="whisper-1"
    )

# Extract transcript text
transcript_text = transcript.text

# Print to console for verification
print(transcript_text)

pdf = FPDF()
pdf.add_page()
pdf.set_auto_page_break(auto=True, margin=15)


pdf.add_font('NotoSansTC', '', '/Users/kevinc220/Downloads/Noto_Sans_TC/NotoSansTC-VariableFont_wght.ttf', uni=True)
pdf.set_font('NotoSansTC', '', 12)

# Split text into lines to avoid overflow
for line in transcript_text.split('\n'):
    pdf.multi_cell(0, 10, line)

# Output to PDF file
pdf.output("02議事規則擬訂作業及健保新藥核價作業說明-transcript.pdf")

print("complete")