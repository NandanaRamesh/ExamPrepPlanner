import streamlit as st
from PyPDF2 import PdfReader
import google.generativeai as genai
from io import BytesIO

GEMINI_API_KEY = "AIzaSyDO4Jy1s_pTxg9y6qEFZNMfnPPYfmJ6A98"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file."""
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def summarize_text(text):
    """
    Summarizes text in an exam-oriented format using the Gemini API.
    
    Parameters:
    - text (str): The text to summarize.
    - model: The Gemini API model instance to generate content.
    
    Returns:
    - str: The summarized text in an exam-friendly format.
    """
    prompt = (
        f"Summarize the following text into concise, exam-oriented notes. "
        f"Focus on definitions, key concepts, and important points, and provide the summary in bullet point format:\n\n{text}"
    )
    response = model.generate_content(prompt)
    summary = response.text
    return summary


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

def adjust_history_for_gemini(history):
    """Adjusts chat history for Gemini API."""
    return [{"role": message["role"], "parts": [message["content"]]} for message in history]

# Sidebar chatbot functionality
def chatbot_with_scroll_and_gemini():
    st.markdown("## 🤖 Doubt Clearance Chatbot")

    # Initialize chat history in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages with scroll
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Keep the input bar fixed at the bottom
    user_input = st.chat_input("Ask a question...")
    if user_input:
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)

        # Save user's message to session state
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Generate a response using Gemini API
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            try:
                # Start a conversation with Gemini
                formatted_history = adjust_history_for_gemini(st.session_state.messages)
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(user_input)

                # Update the full response dynamically
                full_response = response.text
                message_placeholder.markdown(full_response)

                # Save assistant's response to session state
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"Error in communication with Gemini API: {e}")

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
    st.title("Revision Notes")

    st.write("Welcome to the Revision Notes page!")
    st.markdown("### Revision Notes")

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

    # Display Summary and Flashcards together
    if summary:
        st.subheader("Summary")
        st.markdown(summary)

    # Section: Flashcards
    st.subheader("Flashcards")
    flashcards = ""
    if extracted_text:
        if st.button("Generate Flashcards"):
            flashcards = generate_flashcards(extracted_text)


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

    # Section: Search
    st.subheader("Search Notes")
    search_query = st.text_input("Enter search query")
    if search_query and extracted_text:
        search_results = [line for line in extracted_text.split('\n') if search_query.lower() in line.lower()]
        st.write("Search Results:")
        for result in search_results:
            st.write(f"- {result}")

    chatbot_with_scroll_and_gemini()
