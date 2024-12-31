import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# Accessing Supabase credentials from secrets
supabase_url = st.secrets["supabase"]["url"]
supabase_key = st.secrets["supabase"]["key"]

# Creating a Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

# Set up the page configuration
st.set_page_config(page_title="Exam Prep Planner", layout="wide")

# Sidebar menu - Conditionally Display Based on User Sign-In
if "user_logged_in" not in st.session_state or not st.session_state["user_logged_in"]:
    menu = ["Home", "Signup/Login"]
else:
    menu = ["Home", "Upload Syllabus", "AI Doubt Clearing", "Revision Notes", "Interactive Schedule"]

# Display buttons in the sidebar for navigation
st.sidebar.title("Exam Prep Planner")

# Create a custom navigation in the sidebar
for menu_item in menu:
    if st.sidebar.button(menu_item):
        st.session_state["selected_page"] = menu_item

# Sidebar footer
st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ for Exam Prep")


# Function to handle login
def login():
    st.markdown("### Login")
    user_email = st.text_input("Enter your email")
    password = st.text_input("Enter your password", type="password")

    if st.button("Login"):
        if user_email and password:
            try:
                # Log in the user with Supabase Auth
                response = supabase.auth.sign_in_with_password({
                    "email": user_email,
                    "password": password
                })

                # Access the user object using dot notation
                if response.user:
                    st.success(f"Welcome back, {response.user.email}!")
                    st.session_state["user_logged_in"] = True
                    st.session_state["user_name"] = response.user.email
                    st.session_state["selected_page"] = "Home"  # Navigate to Home page
                    st.rerun()  # Refresh after login
                else:
                    st.error("Invalid credentials. Please try again.")

            except Exception as e:
                st.error(f"Login failed: {e}")
        else:
            st.error("Please fill in both fields.")

    # Link to signup page
    if st.button("Don't have an account? Sign Up"):
        st.session_state["show_signup"] = True
        st.session_state["show_login"] = False
        st.session_state["selected_page"] = "Signup/Login"  # Show signup page
        st.rerun()


# Function to handle signup
def sign_up():
    st.markdown("### Sign Up")

    user_name = st.text_input("Enter your username")
    user_email = st.text_input("Enter your email")
    password = st.text_input("Enter your password", type="password")
    confirm_password = st.text_input("Confirm your password", type="password")

    if st.button("Sign Up"):
        if user_name and user_email and password and confirm_password:
            if password == confirm_password:
                try:
                    # Sign up the user with Supabase Auth
                    response = supabase.auth.sign_up(
                        {"email": user_email, "password": password}  # Pass email and password inside a dictionary
                    )

                    # Check if the response contains a user
                    user = response.user  # This is where you get the user info (not response["user"])

                    if user:
                        # Fetch the UID from the user object
                        user_uid = user.id  # The user object contains an 'id' field for the UID

                        # If UID exists, insert the username into the "usernames" table
                        if user_uid:
                            # Insert into the "usernames" table
                            insert_response = supabase.from_("usernames").insert({
                                "UID": user_uid,
                                "username": user_name
                            }).execute()

                            # Now check if the username and UID are properly inserted
                            check_response = supabase.from_("usernames").select("*").eq("UID", user_uid).eq("username",
                                                                                                            user_name).execute()

                            if check_response.data and len(check_response.data) > 0:
                                st.success(
                                    f"Account created successfully, {user_name}! Please check your email to verify your account.")
                            else:
                                st.error("Error saving username to the database.")
                        else:
                            st.error("Error: UID not found. Unable to update username.")
                    else:
                        st.error("Error: Unable to fetch user details from Supabase.")

                        # Show a login prompt and clear session data
                        if "user_logged_in" in st.session_state:
                            del st.session_state["user_logged_in"]
                        if "user_name" in st.session_state:
                            del st.session_state["user_name"]

                        st.markdown("Please verify your email to complete the signup process.")
                        st.markdown("Once your email is verified, you can log in.")

                        # Option to go to the login page
                        if st.button("Go to Login"):
                            st.session_state["selected_page"] = "Signup/Login"
                            st.rerun()

                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Passwords do not match.")
        else:
            st.error("Please fill in all fields.")

    # Link to login page
    if st.button("Already have an account? Login"):
        st.session_state["show_signup"] = False
        st.session_state["show_login"] = True
        st.session_state["selected_page"] = "Signup/Login"  # Show login page
        st.rerun()


# Top Section
if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "Home"

selection = st.session_state["selected_page"]

if selection == "Home":
    if "user_logged_in" not in st.session_state or not st.session_state["user_logged_in"]:
        # User Not Signed In
        st.markdown("""
            <style>
                .welcome-banner {
                    text-align: center;
                    padding: 40px;
                    background-color: #333;
                    border-radius: 10px;
                    margin-bottom: 30px;
                    font-family: Arial, sans-serif;
                    color: #f0f0f0;
                }
                .info-card {
                    border: 1px solid #444;
                    border-radius: 10px;
                    padding: 20px;
                    background-color: #2a2a2a;
                    margin-bottom: 20px;
                    text-align: center;
                    color: #ffffff;
                }
                h1, h4, p {
                    margin: 0;
                }
            </style>
        """, unsafe_allow_html=True)

        # Welcome Banner
        st.markdown(
            '<div class="welcome-banner">'
            '<h1>Welcome to Exam Prep Planner!</h1>'
            '<p>Your personalized tool for study schedules, revision notes, and AI-powered doubt clearing.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Flashcard-Style Info Cards
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="info-card"><h4>Upload Syllabus</h4><p>Get a personalized study schedule in seconds!</p></div>', unsafe_allow_html=True)
            st.markdown('<div class="info-card"><h4>AI-Powered Doubt Clearing</h4><p>Ask questions, get answers instantly!</p></div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="info-card"><h4>Revision Notes</h4><p>Summarized key topics for efficient prep!</p></div>', unsafe_allow_html=True)
            st.markdown('<div class="info-card"><h4>Interactive Schedule</h4><p>Plan and manage tasks with ease!</p></div>', unsafe_allow_html=True)

        # Call-to-Action Section
        st.markdown("<hr>", unsafe_allow_html=True)
        if st.button("Sign Up to Get Started"):
            st.session_state["show_signup"] = True
            st.session_state["selected_page"] = "Signup/Login"  # Navigate to Signup
            st.rerun()  # Refresh to show signup form

    else:
        # User Signed In
        st.write(f"Welcome back, **{st.session_state['user_name']}**! Let's crush your exams!")

        # Dashboard Cards
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Upcoming Exams/Projects", "2 Exams", "5 Days Left")

        with col2:
            st.metric("Today's Study Schedule", "3 Tasks", "On Track")

        with col3:
            st.metric("Overall Progress", "50%", "+10% This Week")

        # Upload Syllabus Section
        st.markdown("### Upload or Copy-Paste Your Syllabus")
        col1, col2 = st.columns(2)

        with col1:
            uploaded_file = st.file_uploader("Upload File")

        with col2:
            syllabus_text = st.text_area("Paste Syllabus Here")

        if st.button("Generate Study Plan"):
            st.success("Study Plan Generated Successfully!")

elif selection == "Signup/Login":
    # Check if the user wants to see the signup page or the login page
    if st.session_state.get("show_signup", False):
        sign_up()  # Show the signup form
    else:
        login()  # Show the login form

elif selection == "Upload Syllabus":
    st.markdown("### Upload Your Syllabus")
    uploaded_file = st.file_uploader("Choose a file")
    if uploaded_file:
        st.write("File uploaded successfully!")

elif selection == "AI Doubt Clearing":
    st.markdown("### AI Doubt Clearing")
    user_query = st.text_input("Ask a question:")
    if user_query:
        st.write(f"AI Response: [Simulated answer for '{user_query}']")

elif selection == "Revision Notes":
    st.markdown("### Revision Notes")
    st.write("Your summarized key topics will appear here.")

elif selection == "Interactive Schedule":
    st.markdown("### Interactive Schedule")
    st.write("Manage and plan your tasks effectively here.")
