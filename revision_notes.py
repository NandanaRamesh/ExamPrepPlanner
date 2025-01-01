import streamlit as st
from PyPDF2 import PdfReader
import google.generativeai as genai
from io import BytesIO

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyDO4Jy1s_pTxg9y6qEFZNMfnPPYfmJ6A98"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file."""
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def summarize_text(text):
    """Summarizes text using the Gemini API."""
    response = model.generate_content(f"Summarize the following text:\n{text}")
    return response.text

def generate_flashcards(text):
    """Generates flashcards using the Gemini API."""
    response = model.generate_content(f"Create flashcards for the following text:\n{text}")
    return response.text

def highlight_key_points(text, key_points):
    """Highlights key points in the original text."""
    highlighted = text
    for point in key_points:
        highlighted = highlighted.replace(point, f"**{point}**")
    return highlighted

def chat_with_gemini(question, chat_history):
    """Handles chat conversation with Gemini API."""
    chat = model.start_chat(history=chat_history)
    response = chat.send_message(question)
    return response.text, chat.history

# HTML and CSS for flip cards
flip_card_html = """
<style>
.flip-card-container {{
  display: flex;
  flex-wrap: wrap;
  justify-content: space-evenly;
  gap: 20px;
  margin-top: 20px;
}}

.flip-card {{
  background-color: transparent;
  margin: 5px;
  width: 300px;
  height: 200px;
  perspective: 1000px;
  border-radius: 10px;
  padding: 10px;
}}

.flip-card-inner {{
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.6s;
}}

.flip-card:hover .flip-card-inner {{
  transform: rotateY(180deg);
}}

.flip-card-front, .flip-card-back {{
  position: absolute;
  width: 100%;
  height: 100%;
  backface-visibility: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  border-radius: 8px;
}}

.flip-card-front {{
  background-color: #f0f0f5;
  color: black;
}}

.flip-card-back {{
  background-color: #000000;
  color: white;
  transform: rotateY(180deg);
}}
</style>

<div class="flip-card-container">
  <div class="flip-card">
    <div class="flip-card-inner">
      <div class="flip-card-front">
        {front_text}
      </div>
      <div class="flip-card-back">
        {back_text}
      </div>
    </div>
  </div>
</div>
"""

# Streamlit UI
def show_revision_notes():
    st.markdown("### Revision Notes")
    st.write("Welcome to the Revision Notes page!")

    # Section: Upload Notes
    st.subheader("Upload Notes")
    uploaded_file = st.file_uploader("Upload your notes here (PDF only)", type=["pdf"])
    extracted_text = ""
    if uploaded_file:
        extracted_text = extract_text_from_pdf(uploaded_file)
        st.success(f"Uploaded file: {uploaded_file.name}")
        st.text_area("Extracted Text", extracted_text, height=200)

    # Section: Summarizer
    st.subheader("Summarizer")
    summary = ""
    if extracted_text:
        if st.button("Summarize Notes"):
            summary = summarize_text(extracted_text)
    
    # Section: Flashcards
    flashcards = ""
    if extracted_text:
        if st.button("Generate Flashcards"):
            flashcards = generate_flashcards(extracted_text)

    # Display Summary and Flashcards together
    if summary:
        st.subheader("Summary")
        st.text_area("Summary", summary, height=150)
    
    if flashcards:
        st.subheader("Flashcards")
        # Split the flashcards into individual cards (assuming each card is split by new lines or some separator)
        flashcard_lines = flashcards.split('\n')
        for i in range(0, len(flashcard_lines), 2):
            # Ensure front and back text are clean
            card_front = flashcard_lines[i].strip() if i < len(flashcard_lines) else ""
            card_back = flashcard_lines[i+1].strip() if i+1 < len(flashcard_lines) else ""
            
            # Ensure that both card front and back text are not empty
            if card_front and card_back:
                # Text after the ** will be displayed as the front text
                front_text = card_front.split("**")[-1].strip()
                back_text = card_back.split("**")[-1].strip()
                
                # Generate the flip card HTML for each flashcard
                card_html = flip_card_html.format(front_text=front_text, back_text=back_text)
                st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.write("")

    # Section: Search
    st.subheader("Search Notes")
    search_query = st.text_input("Enter search query")
    if search_query and extracted_text:
        search_results = [line for line in extracted_text.split('\n') if search_query.lower() in line.lower()]
        st.write("Search Results:")
        for result in search_results:
            st.write(f"- {result}")

    # Section: Ask Doubts
    st.subheader("Ask Questions")
    question = st.text_input("Ask a question about your notes")
    if question and extracted_text:
        chat_history = [{"role": "user", "parts": extracted_text}]
        response, chat_history = chat_with_gemini(question, chat_history)
        st.write("Response:")
        st.write(response)

    # Highlight Key Points
    st.subheader("Highlighted Key Points")
    if search_query:
        highlighted_text = highlight_key_points(extracted_text, search_results)
        st.text_area("Highlighted Text", highlighted_text, height=200)
