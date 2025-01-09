import streamlit as st
from PyPDF2 import PdfReader
import google.generativeai as genai
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from supabase import create_client, Client

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyDO4Jy1s_pTxg9y6qEFZNMfnPPYfmJ6A98"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Accessing Supabase credentials from secrets
supabase_url = st.secrets["supabase"]["url"]
supabase_key = st.secrets["supabase"]["key"]

# Creating a Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

def fetch_notes_history(email):
    try:
        response = supabase.table("History").select("*").eq("email", st.session_state["user_name"]).execute()

        # Return the notes data
        return response.data or []
    except Exception as e:
        st.error(f"An unexpected error occurred while fetching notes: {e}")
        return []

def add_note_to_history(email, note_name):
    try:
        # Fetch the last inserted ID from the table
        last_entry = supabase.table("History").select("id").order("id", desc=True).limit(1).execute()
        last_id = last_entry.data[0]["id"] if last_entry.data else None

        # Generate the new ID
        if last_id:
            # Extract numeric part and increment it
            numeric_part = int(last_id[1:])  # Skip the first character (e.g., "H")
            new_id = f"H{numeric_part + 1:06d}"  # Zero-padded to 6 digits
        else:
            # If no ID exists, start with H000001
            new_id = "H000001"

        # Insert the new note into the database
        response = supabase.table("History").insert(
            {"id": new_id, "email": st.session_state["user_name"], "note_name": note_name}
        ).execute()

        return response
    except Exception as e:
        st.error(f"An unexpected error occurred while adding a note: {e}")
        return None


def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file."""
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def summarize_text(text, note_name):
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
    email = st.session_state.get("user_name")

    # Generate a new summary
    response = model.generate_content(prompt)
    summary = response.text

    # Save the summary to the database
    save_summary_to_database(email, note_name, summary)

    # Display the new summary
    # st.markdown("New Summary", summary, height=150, key="new_summary")

    # Provide download options for the new summary
    st.download_button(
        label="Download as TXT",
        data=summary,
        file_name=f"{note_name}_summary.txt",
        mime="text/plain"
    )

    # Generate a downloadable PDF
    pdf_buffer = BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(pdf_buffer)

    # Prepare styled content for the PDF
    content = []
    for line in summary.split("\n"):
        if line.startswith("**") and line.endswith("**"):
            line = f"<b>{line[2:-2]}</b>"
        elif line.startswith("*   "):  # Handle bullet points
            line = f"<bullet>&bull;</bullet> {line[4:]}"
        content.append(Paragraph(line, styles["Normal"]))
        content.append(Spacer(1, 12))  # Add spacing between paragraphs

    doc.build(content)
    pdf_buffer.seek(0)

    st.download_button(
        label="Download as PDF",
        data=pdf_buffer,
        file_name=f"{note_name}_summary.pdf",
        mime="application/pdf"
    )

    st.success("Summary generated and saved successfully!")

def save_summary_to_database(email, note_name, summary):
    try:
        # Check if a summary already exists for the given note name
        response = supabase.table("Summaries").select("*").eq("email", email).eq("note_name", note_name).execute()

        if response.data:
            # Update the existing summary
            existing_id = response.data[0]["id"]
            update_response = supabase.table("Summaries").update({
                "summary": summary
            }).eq("id", existing_id).execute()
            st.rerun()  # Rerun the app to display the updated summary
        else:
            # Generate a new ID
            last_entry = supabase.table("Summaries").select("id").order("id", desc=True).limit(1).execute()
            last_id = last_entry.data[0]["id"] if last_entry.data else None
            if last_id:
                numeric_part = int(last_id[3:])
                new_id = f"SUM{numeric_part + 1:06d}"
            else:
                new_id = "SUM000001"

            # Insert the new summary
            insert_response = supabase.table("Summaries").insert({
                "id": new_id,
                "email": email,
                "note_name": note_name,
                "summary": summary
            }).execute()
            st.rerun()  # Rerun the app to display the new summary
    except Exception as e:
        st.error(f"An unexpected error occurred while saving the summary: {e}")


def generate_flashcards(text):
    """Generates flashcards using the Gemini API."""
    response = model.generate_content(f"Create flashcards for the following text, give me only question and answers and nothing else:\n{text}")
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

    # Check if user is logged in
    email = st.session_state.get("user_name")
    if not email:
        st.error("User not logged in. Please log in to access notes.")
        return

    # Retrieve user's notes from Supabase
    notes_history = fetch_notes_history(email)

    # Step 1: Handle navigation between notes list and note details
    if "current_note" not in st.session_state or st.session_state.current_note is None:
        st.subheader("Select or Create a Note")

        # Display existing notes
        if notes_history:
            st.write("Select an existing note:")
            selected_note = st.selectbox("Existing Notes", [note["note_name"] for note in notes_history])

            if st.button("Open Note", key="open_note_button"):
                st.session_state.current_note = selected_note
                st.rerun()

        else:
            st.write("No existing notes found. Please create a new note.")

        # Create a new note
        new_note_name = st.text_input("Enter a new note name:")
        if st.button("Create Note", key="create_note_button"):
            if new_note_name.strip():
                add_note_response = add_note_to_history(email, new_note_name)
                if add_note_response.data:
                    st.session_state.current_note = new_note_name
                    st.success(f"Note '{new_note_name}' created successfully!")
                    st.session_state.current_note = new_note_name
                    st.rerun()
                else:
                    error_message = (
                        add_note_response.error.get("message", "Unknown error")
                        if add_note_response.error
                        else "Unknown error"
                    )
                    st.error(f"Failed to create note: {error_message}")
            else:
                st.error("Note name cannot be empty.")

    else:
        # Step 2: Show the selected note details
        st.subheader(f"Working on Note: {st.session_state.current_note}")

        # Add a "Back" button to return to the notes list
        if st.button("< Back to Notes List", key="back_to_notes_button"):
            st.session_state.current_note = None
            st.rerun()

        # Section: Upload Notes
        st.subheader("Upload Notes")
        uploaded_file = st.file_uploader("Upload your notes here (PDF only)", type=["pdf"])
        extracted_text = ""
        email = st.session_state.get("user_name")
        note_name = st.session_state.get("current_note")

        # Function to check if a file already exists in the Supabase bucket
        def fetch_file_from_bucket(email, note_name):
            """Fetches the file from the Supabase bucket if it exists."""
            file_path = f"{email}/{note_name}.pdf"  # File path in the bucket
            try:
                # Attempt to retrieve the file
                response = supabase.storage.from_("Files").download(file_path)
                if response:
                    return response
            except Exception as e:
                st.warning(f"Could not fetch file from bucket '{file_path}': {e}")
            return None

        # Function to upload a file to the Supabase bucket
        def upload_file_to_bucket(file, email, note_name):
            """Uploads the file to the Supabase bucket."""
            file_path = f"{email}/{note_name}.pdf"
            try:
                # Upload file content to the bucket
                supabase.storage.from_("Files").upload(file_path, file.read())
                st.success(f"File successfully uploaded as {file_path}")
            except Exception as e:
                st.error(f"Error uploading file: {e}")

        # Check for an existing file in the bucket
        existing_file = fetch_file_from_bucket(email, note_name)
        if existing_file:
            # If file exists, process it directly in memory
            st.info(f"A file already exists for this note: {note_name}.pdf")

            # Use BytesIO to hold the file content in memory
            file_content = BytesIO(existing_file)
            extracted_text = extract_text_from_pdf(file_content)
            st.text_area("Extracted Text from Existing File", extracted_text, height=200)
        else:
            # Handle file upload if no existing file is found
            if uploaded_file:
                # Display uploaded file details
                st.success(f"Uploaded file: {uploaded_file.name}")

                # Save the uploaded file to the Supabase bucket
                upload_file_to_bucket(uploaded_file, email, note_name)

                # Extract text from the uploaded file in memory
                extracted_text = extract_text_from_pdf(uploaded_file)
                st.text_area("Extracted Text", extracted_text, height=200)

        # Section: Summarizer
        st.subheader("Summarizer")
        email = st.session_state.get("user_name")
        note_name = st.session_state.current_note

        # Check for existing summary
        response = supabase.table("Summaries").select("summary").eq("email", email).eq("note_name", note_name).execute()
        existing_summary = response.data[0]["summary"] if response.data else None

        # Display existing summary or a message if none exists
        if existing_summary:
            st.text_area("Summary", existing_summary, height=350, disabled=True)
            st.download_button(
                label="Download Summary as TXT",
                data=existing_summary,
                file_name=f"{note_name}_summary.txt",
                mime="text/plain"
            )
        else:
            st.write("No previous history of a Summary.")

        # Always include the button to generate a new summary
        if st.button("Summarize Notes", key="summarize_notes_button"):
            if extracted_text.strip():
                summarize_text(extracted_text, note_name)
                st.rerun()  # Refresh the page to show the new summary
            else:
                st.error("No text provided for summarization.")

        # Section: Flashcards
        st.subheader("Flashcards")
        flashcards = ""
        if extracted_text:
            if st.button("Generate Flashcards", key="generate_flashcards_button"):
                flashcards = generate_flashcards(extracted_text)

        if flashcards:
            st.subheader("Flashcards")
            # Split the flashcards into individual cards
            flashcard_lines = flashcards.split('\n')
            for i in range(0, len(flashcard_lines), 2):
                card_front = flashcard_lines[i].strip() if i < len(flashcard_lines) else ""
                card_back = flashcard_lines[i + 1].strip() if i + 1 < len(flashcard_lines) else ""
                if card_front and card_back:
                    front_text = card_front.split("**")[-1].strip()
                    back_text = card_back.split("**")[-1].strip()
                    card_html = flip_card_html.format(front_text=front_text, back_text=back_text)
                    st.markdown(card_html, unsafe_allow_html=True)

        # Section: Search
        st.subheader("Search Notes")
        search_query = st.text_input("Enter search query")
        if search_query and extracted_text:
            search_results = [
                line for line in extracted_text.split('\n') if search_query.lower() in line.lower()
            ]
            st.write("Search Results:")
            for result in search_results:
                st.write(f"- {result}")

        # Include chatbot functionality
        chatbot_with_scroll_and_gemini()
