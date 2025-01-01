import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
from revision_notes import show_revision_notes
import pandas as pd
import calendar

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
    menu = ["Home", "Schedule Maker", "Revision Notes", "Settings", "Logout"]

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


# Function to handle logout
def logout():
    st.session_state["user_logged_in"] = False
    st.session_state["user_name"] = ""
    st.session_state["selected_page"] = "Home"  # Navigate to Home page
    st.session_state["show_signup"] = False
    st.session_state["show_login"] = False
    st.session_state.clear()  # Clear all session data
    st.rerun()


# Helper function to add ordinal suffix to week number
def ordinal(n):
    return "%d%s" % (n, "tsnrhtdd"[((n // 10 % 10 != 1) * (n % 10 < 4) * n % 10)::4])

def add_task(date, task):
    user = supabase.auth.user()  # Get the logged-in user
    if user:  # Ensure the user is logged in
        try:
            # Insert the task into the Supabase database with UID
            response = supabase.table("Tasks").insert({
                "UID": user.id,
                "date": date.strftime('%Y-%m-%d'),  # Store the date as a string in the format YYYY-MM-DD
                "task": task,
                "created_at": datetime.now().isoformat()  # Automatically set the created_at field to the current time
            }).execute()

            # Check if the insertion was successful by checking the response
            if response.data:  # If there's data in the response, it means success
                st.success(f"Task added for {date.strftime('%Y-%m-%d')}")
            else:
                st.error(f"Error adding task: {response.error_message}")
        except Exception as e:
            st.error(f"Error adding task: {e}")
    else:
        st.error("User not logged in. Please log in to add tasks.")

# Function to show Month View Calendar
def show_month_calendar(current_date):
    # Get the month days (weeks)
    month_days = calendar.monthcalendar(current_date.year, current_date.month)

    # Display Month and Year at the top
    st.markdown(f"## {current_date.strftime('%B %Y')}")

    # Day names header (Mon, Tue, Wed, ...)
    days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cols = st.columns(7)
    for i, day_name in enumerate(days_header):
        cols[i].markdown(f"**{day_name}**")

    # Add the dates for the month in grid format
    clicked_date = None
    for week in month_days:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                date = datetime(current_date.year, current_date.month, day)
                date_str = date.strftime('%Y-%m-%d')

                # Create a button for each day and track task status
                task_button_color = "lightgreen" if date in st.session_state.get("tasks", {}) else "lightblue"
                button = cols[i].button(f"{day}", key=f"day_button_{date_str}")
                if button:
                    clicked_date = date

    # Show the task input below the calendar for the clicked date
    if clicked_date:
        task_input = st.text_input(f"Add task for {clicked_date.strftime('%Y-%m-%d')}")
        if st.button(f"Add Task for {clicked_date.strftime('%Y-%m-%d')}"):
            if task_input.strip():
                add_task(clicked_date, task_input.strip())

# Function to show Week View Calendar
def show_week_calendar(current_date):
    # Get the start of the current week
    start_of_week = current_date - timedelta(days=current_date.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    # Calculate the week number in the month
    first_day_of_month = datetime(current_date.year, current_date.month, 1)
    week_number = ((start_of_week - first_day_of_month).days // 7) + 1

    # Display the week number
    st.markdown(f"### {ordinal(week_number)} Week of {current_date.strftime('%B')}")

    # Day names header (Mon, Tue, Wed, ...)
    days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cols = st.columns(7)
    for i, day_name in enumerate(days_header):
        cols[i].markdown(f"**{day_name}**")

    # Add the dates for the current week
    cols = st.columns(7)
    for i, date in enumerate(week_dates):
        cols[i].button(f"{date.day}", key=f"week_button_{date.strftime('%Y-%m-%d')}", on_click=add_task, args=(date,))

# Function to show Day View Calendar
def show_day_calendar(current_date):
    # Get the current day's name
    day_name = calendar.day_name[current_date.weekday()]  # "Monday", "Tuesday", etc.

    # Simple Day View Layout
    st.markdown(f"### {day_name}, {current_date.strftime('%B %d, %Y')}")

    # Display tasks for the selected day
    st.markdown("#### Tasks:")
    tasks = fetch_tasks_for_day(current_date)  # Fetch tasks from Supabase for this day
    if tasks:
        for task in tasks:
            st.markdown(f"- {task['task']}")
    else:
        st.markdown("_No tasks added yet._")

    # Input box and button for adding tasks
    st.markdown("#### Add a New Task:")
    task_input = st.text_input("Enter your task:", key=f"task-input-{current_date}")
    if st.button(f"Add Task for {current_date.strftime('%Y-%m-%d')}"):
        if task_input.strip():  # Only add non-empty tasks
            add_task(current_date, task_input.strip())
            st.rerun()


# Function to fetch tasks for a specific date from Supabase
def fetch_tasks_for_day(date):
    response = supabase.table("Tasks").select("*").eq("date", date.strftime('%Y-%m-%d')).execute()

    # If there is valid data in the response, return it
    if response.data:
        return response.data
    else:
        st.error("No tasks found for this date.")
        return []

# Function to display the calendar and interact with tasks
def display_calendar():
    st.markdown("### Interactive Calendar")

    # Get current date for default view
    current_date = datetime.now()

    # Get view option: Day, Week, Month
    view_option = st.radio("Choose view", ("Day View", "Week View", "Month View"))

    # Generate the calendar based on the selected view
    if view_option == "Month View":
        show_month_calendar(current_date)
    elif view_option == "Week View":
        show_week_calendar(current_date)
    elif view_option == "Day View":
        show_day_calendar(current_date)

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
            st.markdown(
                '<div class="info-card"><h4>Upload Syllabus</h4><p>Get a personalized study schedule in seconds!</p></div>',
                unsafe_allow_html=True)
            st.markdown(
                '<div class="info-card"><h4>AI-Powered Doubt Clearing</h4><p>Ask questions, get answers instantly!</p></div>',
                unsafe_allow_html=True)

        with col2:
            st.markdown(
                '<div class="info-card"><h4>Revision Notes</h4><p>Summarized key topics for efficient prep!</p></div>',
                unsafe_allow_html=True)
            st.markdown(
                '<div class="info-card"><h4>Interactive Schedule</h4><p>Plan and manage tasks with ease!</p></div>',
                unsafe_allow_html=True)

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

elif selection == "Schedule Maker":
    display_calendar()

elif selection == "Revision Notes":
    show_revision_notes()

elif selection == "Settings":
    st.markdown("### Settings")
    st.write("Options to manage themes, update profile, and configure notifications.")

elif selection == "Logout":
    logout()
