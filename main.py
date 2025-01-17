import streamlit as st
import re
import time
from supabase import create_client, Client
from datetime import datetime, timedelta
from revision_notes import show_revision_notes
import google.generativeai as genai
import calendar
import os


# Accessing Supabase credentials from secrets
supabase_url = os.environ.get("supabase_url")
supabase_key = os.environ.get("supabase_key")

# Creating a Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

user_mail = None

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

# Configure Gemini API
GEMINI_API_KEY = os.environ.get("google_key")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

# Sidebar footer
st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ for Exam Prep")


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

                if response.user:
                    # Set session data with the returned access and refresh tokens
                    access_token = response.session.access_token
                    refresh_token = response.session.refresh_token

                    # Set session tokens to maintain the user's login state
                    supabase.auth.set_session(access_token, refresh_token)

                    # Store user email, UID, and logged-in state in session state
                    st.session_state["user_name"] = response.user.email  # Store user email
                    st.session_state["user_uid"] = response.user.id  # Store user UID
                    st.session_state["user_logged_in"] = True  # Mark as logged in

                    # Redirect to Home page after successful login
                    st.session_state["selected_page"] = "Home"  # Set selected page to Home
                    st.rerun()  # Rerun to refresh the page and show the Home page

                    st.success(f"Welcome back, {response.user.email}!")
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
                    user = response.user  

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


def logout():
    st.session_state["user_logged_in"] = False
    st.session_state["user_name"] = ""
    st.session_state["selected_page"] = "Home"  # Navigate to Home page
    st.session_state["show_signup"] = False
    st.session_state["show_login"] = False
    st.rerun()


# Helper function to add ordinal suffix to week number
def ordinal(n):
    return "%d%s" % (n, "tsnrhtdd"[((n // 10 % 10 != 1) * (n % 10 < 4) * n % 10)::4])


# function to add task
def add_task(date, task, user_email):
    try:
        # Convert the datetime object to a date object
        task_date = date.date()

        # Fetch the last UID from the Tasks table
        response = supabase.table("Tasks").select("UID").order("UID", desc=True).limit(1).execute()

        # Determine the next UID
        if response.data and len(response.data) > 0:
            last_uid = response.data[0]["UID"]  # e.g., "UID00001"
            # Extract the numeric part and increment it
            last_number = int(last_uid[3:])  # Skip the "UID" prefix
            next_number = last_number + 1
        else:
            next_number = 1  # Start with 1 if no records exist

        # Format the new UID with leading zeros and the "UID" prefix
        next_uid = f"UID{next_number:05d}"

        # Insert the new task into the table with the generated UID
        insert_response = supabase.table("Tasks").insert({
            "UID": next_uid,  # Formatted UID
            "email": user_email,
            "date": task_date.strftime('%Y-%m-%d'),
            "task": task,
            "completion": "false",
        }).execute()

    except Exception as e:
        st.error(f"Unexpected error: {e}")

def show_month_calendar(current_date):
    # Initialize session state keys if not already present
    if "clicked_month_date" not in st.session_state:
        # Set the clicked month date to the first day of the current month
        first_day_of_month = datetime(current_date.year, current_date.month, 1)
        st.session_state["clicked_month_date"] = first_day_of_month
        # Fetch tasks for the first day of the month
        st.session_state["tasks_for_selected_date"] = fetch_tasks_for_day(first_day_of_month,
                                                                          st.session_state["user_name"])

    if "tasks_for_selected_date" not in st.session_state:
        st.session_state["tasks_for_selected_date"] = None

    # Get the month days (weeks)
    month_days = calendar.monthcalendar(current_date.year, current_date.month)

    # Display Month and Year at the top
    st.markdown(f"## {current_date.strftime('%B %Y')}")

    # Day names header (Mon, Tue, Wed, ... )
    days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cols = st.columns(7)
    for i, day_name in enumerate(days_header):
        cols[i].markdown(f"**{day_name}**")

    # Add the dates for the month in grid format
    for week in month_days:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:  # Skip empty days
                date = datetime(current_date.year, current_date.month, day)
                date_str = date.strftime('%Y-%m-%d')

                # Fetch task information only once per render for efficiency
                tasks = fetch_tasks_for_day(date, st.session_state["user_name"])
                has_task = len(tasks) > 0

                # Set the cell background color
                cell_style = f"""
                    background-color: {"#FFFFFF" if has_task else "transparent"}; 
                    padding: 5px;
                    border-radius: 5px;
                """

                # Render the styled cell with the button inside
                with cols[i]:
                    st.markdown(
                        f"<div style='{cell_style} display: flex; justify-content: center; align-items: center;'>",
                        unsafe_allow_html=True)
                    if st.button(f"{day}", key=f"btn-{date_str}"):
                        # Save the selected date and its tasks to session state
                        st.session_state["clicked_month_date"] = date
                        st.session_state["tasks_for_selected_date"] = tasks
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    # Only show task-related content if a date is selected
    clicked_date = st.session_state["clicked_month_date"]
    if clicked_date is not None:
        tasks = st.session_state["tasks_for_selected_date"]

        # Task section is rendered only if a date is selected
        st.markdown(f"### Tasks for {clicked_date.strftime('%A, %B %d, %Y')}")
        if tasks:
            st.markdown("#### Existing Tasks:")

            for task in tasks:
                task_uid = task["UID"]  # Unique identifier for the task
                task_done = task["completion"]  # Current completion status

                # Create a checkbox for each task to mark as done, with the current completion status
                task_completed = st.checkbox(f"{task['task']}", key=f"chk-{task_uid}")

                # If the checkbox state has changed, update the task's completion status
                if task_completed != task_done:
                    update_task_completion(task_uid, task_completed)

        else:
            st.markdown("_No tasks added yet._")

        # Input field for adding tasks
        st.markdown("#### Add a New Task:")
        task_input = st.text_input("Enter your task")
        if st.button(f"Add Task for {clicked_date.strftime('%Y-%m-%d')}"):
            if task_input.strip():
                add_task(clicked_date, task_input.strip(), st.session_state["user_name"])
                st.success(f"Task added for {clicked_date.strftime('%Y-%m-%d')}")
                st.session_state["task_added"] = clicked_date
                st.rerun()
            else:
                st.error("Please enter a valid task.")

def show_week_calendar(current_date):
    # Get the start of the current week
    start_of_week = current_date - timedelta(days=current_date.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    # Calculate the week number in the month
    first_day_of_month = datetime(current_date.year, current_date.month, 1)
    week_number = ((start_of_week - first_day_of_month).days // 7) + 1

    # Display the week number
    st.markdown(f"### {ordinal(week_number)} Week of {current_date.strftime('%B')}")

    # Day names header (Mon, Tue, Wed, ... )
    days_header = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cols = st.columns(7)
    for i, day_name in enumerate(days_header):
        cols[i].markdown(f"**{day_name}**")

    # Initialize session state for clicked week date
    if "clicked_week_date" not in st.session_state:
        # Set the clicked date to the first day of the week initially
        st.session_state["clicked_week_date"] = week_dates[0]

    # Add the dates for the week in grid format
    clicked_date = st.session_state["clicked_week_date"]
    for i, date in enumerate(week_dates):
        date_str = date.strftime('%Y-%m-%d')

        # Fetch task information for the date
        tasks = fetch_tasks_for_day(date, st.session_state["user_name"])
        has_task = len(tasks) > 0

        # Set the cell background color
        cell_style = f"""
            background-color: {"#FFFFFF" if has_task else "transparent"}; 
            padding: 5px; 
            border-radius: 5px;
            display: flex;
            justify-content: center;
            align-items: center;
        """

        # Render the styled cell with the button inside
        with cols[i]:
            st.markdown(f"<div style='{cell_style}'>", unsafe_allow_html=True)
            button = st.button(f"{date.day}", key=f"week_day_button_{date_str}")
            if button:
                clicked_date = date
                st.session_state["clicked_week_date"] = clicked_date
            st.markdown("</div>", unsafe_allow_html=True)

    # Show the task input below the calendar for the clicked date
    if clicked_date is not None:
        st.markdown(f"### Tasks for {clicked_date.strftime('%A, %B %d, %Y')}")
        tasks = fetch_tasks_for_day(clicked_date, st.session_state["user_name"])

        if tasks:
            st.markdown("#### Existing Tasks:")

            for task in tasks:
                task_uid = task["UID"]  # Unique identifier for the task
                task_done = task["completion"]  # Current completion status

                # Create a checkbox for each task to mark as done, with the current completion status
                task_completed = st.checkbox(f"{task['task']}", key=f"task_chk_{task_uid}")

                # If the checkbox state has changed, update the task's completion status
                if task_completed != task_done:
                    update_task_completion(task_uid, task_completed)

        else:
            st.markdown("_No tasks added yet._")

        # Input field for adding tasks
        st.markdown("#### Add a New Task:")
        task_input = st.text_input("Enter your task")

        if st.button(f"Add Task for {clicked_date.strftime('%Y-%m-%d')}"):
            if task_input.strip():
                # Add task for the clicked date
                add_task(clicked_date, task_input.strip(), st.session_state["user_name"])
                # Clear clicked date and rerun
                st.session_state.pop("clicked_week_date", None)
                st.session_state["task_added"] = clicked_date.strftime('%Y-%m-%d')
                st.rerun()
            else:
                st.error("Please enter a valid task.")

    if "task_added" in st.session_state:
        st.success(f"Task added for {st.session_state['task_added']}")
        del st.session_state["task_added"]  # Reset the task_added flag


def show_day_calendar(current_date):
    # Get the current day's name
    day_name = calendar.day_name[current_date.weekday()]  # "Monday", "Tuesday", etc.

    # Simple Day View Layout
    st.markdown(f"### {day_name}, {current_date.strftime('%B %d, %Y')}")

    # Display tasks for the selected day
    st.markdown("#### Tasks:")
    tasks = fetch_tasks_for_day(current_date, st.session_state["user_name"])  # Fetch tasks from Supabase for this day

    if tasks:
        for task in tasks:
            task_uid = task["UID"]  # Unique identifier for the task
            task_done = task["completion"]  # Current completion status

            # Create a checkbox for each task to mark as done, with the current completion status
            task_completed = st.checkbox(f"{task['task']}", key=f"task_chk_{task_uid}")

            # If the checkbox state has changed, update the task's completion status
            if task_completed != task_done:
                update_task_completion(task_uid, task_completed)

    else:
        st.markdown("_No tasks added yet._")

    # Input box for entering a task
    st.markdown("#### Add a New Task:")
    task_input = st.text_input("Enter your task:")

    # Submit button for adding the task
    submit_button = st.button(f"Add Task for {current_date.strftime('%Y-%m-%d')}")

    # Check if the submit button is clicked
    if submit_button:
        if task_input.strip():  # Only add non-empty task
            add_task(current_date, task_input.strip(),
                     st.session_state["user_name"])  # Pass user_email (user_name here)
            st.success("Task added successfully!")  # Notify the user
            st.rerun()  # Rerun the script to update the task list
        else:
            st.error("Please enter a valid task.")  # Notify if the task is empty


# Function to fetch tasks for a specific date and user from Supabase
def fetch_tasks_for_day(date, user_email):
    """
    Fetch tasks for a specific date and user email from the Supabase database.
    """
    response = supabase.table("Tasks").select("task", "date", "UID", "completion") \
        .eq("date", date.strftime('%Y-%m-%d')) \
        .eq("email", user_email).execute()

    # Return the data if it exists
    if response.data:
        return response.data
    else:
        return []  # Return an empty list if no tasks are found


def show_upcoming_tasks():
    """
    Fetch and display upcoming tasks as checklists with an option to update their completion status.
    """
    # Get the current date for filtering tasks
    current_date = datetime.now()
    formatted_date = current_date.strftime('%Y-%m-%d')

    st.markdown(f"### Upcoming Tasks from {current_date.strftime('%B %d, %Y')}")

    # Fetch tasks with date >= current_date for the logged-in user
    try:
        response = (
            supabase.table("Tasks")
            .select("task, date, UID, completion")  # Explicitly specify columns to fetch
            .eq("email", st.session_state["user_name"])  # Match the user email
            .gte("date", formatted_date)  # Filter for tasks with date >= current_date
            .execute()
        )

        # Use .data to access the fetched data
        tasks = response.data if response.data else []

        # Display the tasks as checkboxes
        if tasks:
            for task in tasks:
                task_name = task["task"]
                task_date = task["date"]
                task_uid = task["UID"]
                is_completed = task["completion"] == 'true'

                # Display a checkbox for each task
                new_status = st.checkbox(
                    f"**{task_name}** on {task_date}", value=is_completed
                )

                # Update the task completion status if the checkbox state changes
                if new_status != is_completed:
                    update_task_completion(task_uid, str(new_status).lower())  # Update in database
                    st.rerun()  # Refresh the page to reflect changes
        else:
            st.markdown("_No tasks found._")

    except Exception as e:
        st.error(f"Error fetching tasks: {e}")


def update_task_completion(task_uid, completion_status):
    try:
        response = supabase.table("Tasks").update({"completion": completion_status}).eq("UID",task_uid).execute()
    except Exception as e:
        st.error(f"An error occurred while updating the task completion status: {e}")


def display_calendar():
    st.markdown("### Interactive Calendar")

    # Get current date for default view
    current_date = datetime.now()

    # Get view option: Day, Week, Month, All Upcoming Tasks
    view_option = st.radio("Choose view", ("Day View", "Week View", "Month View", "Upcoming Tasks"))

    # Generate the calendar based on the selected view
    if view_option == "Month View":
        show_month_calendar(current_date)
    elif view_option == "Week View":
        show_week_calendar(current_date)
    elif view_option == "Day View":
        show_day_calendar(current_date)
    elif view_option == "Upcoming Tasks":
        show_upcoming_tasks()


# Function to generate a study plan
def generate_study_plan(syllabus, days_left):
    """
    Generates a study plan in an exam-oriented format using the Gemini API or a similar model.
    
    Parameters:
    - syllabus (str): The syllabus content to analyze and distribute into a study plan.
    - days_left (int): Number of days left for the exam.
    - model: The Gemini API model instance to generate content.
    
    Returns:
    - str: The generated study plan as a string.
    """
    prompt = (
        f"Create a detailed, exam-oriented study plan for the following syllabus, "
        f"distributed over {days_left} days. Prioritize harder topics first, "
        f"and provide daily tasks with specific preparation strategies:\n\n{syllabus}"
    )
    response = model.generate_content(prompt)
    study_plan = response.text
    return study_plan

# Function to generate a study plan
def generate_study_plan(syllabus, days_left):
    """
    Generates a study plan in an exam-oriented format using the Gemini API or a similar model.
    
    Parameters:
    - syllabus (str): The syllabus content to analyze and distribute into a study plan.
    - days_left (int): Number of days left for the exam.
    - model: The Gemini API model instance to generate content.
    
    Returns:
    - str: The generated study plan as a string.
    """
    prompt = (
        f"Create a detailed, exam-oriented study plan for the following syllabus, "
        f"distributed over {days_left} days. Prioritize harder topics first, "
        f"and provide daily tasks with specific preparation strategies in an interesting way:\n\n{syllabus}"
    )
    response = model.generate_content(prompt)
    study_plan = response.text
    return study_plan

def topics_checklist(syllabus):
    """
    Parses the syllabus and generates topics and subtopics as a dictionary.
    """
    prompt = (
        f"Analyze the following syllabus and divide it into main topics. For each main topic, "
        f"list relevant subtopics in a structured format like:\n\n"
        f"1. Main Topic\n"
        f"   - Subtopic 1\n"
        f"   - Subtopic 2\n\n"
        f"Here is the syllabus:\n{syllabus}"
    )
    try:
        # Simulate AI response
        response = model.generate_content(prompt)
        structured_response = response.text  # Assuming text output from AI

        return extract_topics_and_subtopics(structured_response)

    except Exception as e:
        st.error(f"Error generating topics: {e}")
        return None, None


def extract_topics_and_subtopics(data):
    """
    Extracts main topics and subtopics from a structured textual format.
    """

    main_topics = []
    subtopics_by_topic = {}

    try:
        # Regular expression to identify main topics and subtopics
        main_topic_pattern = re.compile(r"^\d+\.\s+(.*)$", re.MULTILINE)
        subtopic_pattern = re.compile(r"^\s*-\s+(.*)$", re.MULTILINE)

        # Split data into lines
        lines = data.splitlines()

        current_main_topic = None
        for line in lines:
            main_topic_match = main_topic_pattern.match(line)
            subtopic_match = subtopic_pattern.match(line)

            if main_topic_match:
                # Extract main topic
                current_main_topic = main_topic_match.group(1).strip()
                main_topics.append(current_main_topic)
                subtopics_by_topic[current_main_topic] = []
            elif subtopic_match and current_main_topic:
                # Extract subtopic under the current main topic
                subtopic = subtopic_match.group(1).strip()
                subtopics_by_topic[current_main_topic].append(subtopic)

    except Exception as e:
        st.error(f"Error parsing topics and subtopics: {e}")

    return main_topics, subtopics_by_topic

# Function to fetch the UID from the 'users' table based on email
def fetch_user_uid(email):
    try:
        response = supabase.table("users").select("UID").eq("email", email).execute()
        if response.data:
            return response.data[0]["UID"]  # Return the UID of the user
        else:
            st.error("User not found in the database.")
            return None
    except Exception as e:
        st.error(f"An error occurred while fetching UID: {e}")
        return None

# Function to fetch the username from the 'usernames' table based on UID
def fetch_username(uid):
    try:
        response = supabase.table("usernames").select("username").eq("UID", uid).execute()
        if response.data:
            return response.data[0]["username"]  # Return the username
        else:
            st.error("Username not found for the given UID.")
            return None
    except Exception as e:
        st.error(f"An error occurred while fetching username: {e}")
        return None

def settings():
    # Tabbed layout for different settings
    tabs = st.tabs(["Manage Themes", "Update Profile", "Configure Notifications"])

    # Tab 1: Change Theme
    with tabs[0]:
        def set_theme(theme_choice):
            config_path = ".streamlit/config.toml"
            theme_config = f"[theme]\nbase = \"{theme_choice}\"\n"

            # Write to config.toml
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as config_file:
                config_file.write(theme_config)

        # Theme Settings UI
        st.markdown("### Theme Settings")
        selected_theme = st.radio("Choose a theme:", ["light", "dark"], index=0)

        if st.button("Apply Theme"):
            set_theme(selected_theme)
            st.rerun()

    # Tab 2: Update Profile
    with tabs[1]:
        st.subheader("Update Profile")

        # Get the current email from session state
        current_email = st.session_state.get("user_name", "")

        # Use Supabase Auth to get the current user and their UID
        def fetch_user_uid():
            if "user_uid" in st.session_state:
                # If the UID is already in session state, return it
                return st.session_state["user_uid"]
            try:
                session = supabase.auth.get_session()  # Correct method to get the session
                if session and session.user:
                    # Log the session details for debugging
                    st.write(f"Session: {session}")  # This will help debug what's inside the session
                    # Store UID in session state
                    st.session_state["user_uid"] = session.user.id
                    return session.user.id  # Return the UID of the current user
                else:
                    st.error("User not found in the session.")
                    return None
            except Exception as e:
                st.error(f"An error occurred while fetching UID: {e}")
                return None

        # Function to fetch username using UID from the 'usernames' table
        def fetch_username(uid):
            try:
                response = supabase.table("usernames").select("username").eq("UID", uid).execute()
                if response.data:
                    return response.data[0]["username"]
                else:
                    st.error("Username not found for the given UID.")
                    return None
            except Exception as e:
                st.error(f"An error occurred while fetching username: {e}")
                return None

        # Fetch UID and username
        user_uid = fetch_user_uid()
        username = fetch_username(user_uid) if user_uid else ""


        # Pre-fill the fields
        name = st.text_input("Name", value=username or "")  # Fallback to empty if username is None
        email = st.text_input("Email", value=current_email)

        if st.button("Update Profile"):
            if name and email:
                try:
                    # Update username in the 'usernames' table
                    if user_uid:
                        response = supabase.table("usernames").update({"username": name}).eq("UID", user_uid).execute()

                        if response.data:  # Check if data is returned, indicating success
                            st.success("Profile updated successfully!")
                            st.session_state["user_name"] = email  # Update email in session state
                        else:
                            st.error("Failed to update the profile. No data returned.")
                    else:
                        st.error("User UID is missing.")
                except Exception as e:
                    st.error(f"An error occurred while updating the profile: {e}")
            else:
                st.error("Both name and email are required to update the profile.")

    # Tab 3: Configure Notifications
    with tabs[2]:
        st.subheader("Configure Notifications")
        reminders = st.checkbox("Enable Study Session Reminders", value=st.session_state.get("reminders", False))

        if st.button("Save Notification Preferences"):
            st.session_state["reminders"] = reminders
            if reminders:
                st.success("Study session reminders enabled!")
            else:
                st.success("Study session reminders disabled!")

# Initialize the selected_page key if it doesn't exist
if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "Home"  # Set default to Home

selection = st.session_state["selected_page"]


# Function to fetch upcoming tasks for a specific user from Supabase
def fetch_upcoming_tasks(user_email):
    """Fetch upcoming tasks from the Tasks table."""
    current_date = datetime.now().strftime('%Y-%m-%d')
    response = supabase.table("Tasks").select("task, date") \
        .eq("email", user_email) \
        .gte("date", current_date) \
        .order("date").execute()  # "asc" for ascending order

    return response.data if response.data else []


# Function to fetch today's tasks for the user
def fetch_todays_tasks(user_email):
    """Fetch tasks for today's date."""
    today_date = datetime.now().strftime('%Y-%m-%d')
    response = supabase.table("Tasks").select("task, date") \
        .eq("email", user_email) \
        .eq("date", today_date).execute()

    return response.data if response.data else []


# Function to fetch the task completion progress
def fetch_task_progress(user_email):
    """Fetch task progress (completed vs total)."""
    response = supabase.table("Tasks").select("completion") \
        .eq("email", user_email).execute()

    # Calculate total tasks and completed tasks based on 'completion' being True (as a boolean or string)
    total_tasks = len(response.data)

    # Adjust the comparison depending on how 'completion' is stored
    completed_tasks = sum(1 for task in response.data if str(task['completion']).lower() == 'true')  # Handle as string

    # Calculate progress percentage (if no tasks exist, return 0%)
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    return total_tasks, completed_tasks, progress_percentage


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
        if "user_uid" in st.session_state:
            user_uid = st.session_state["user_uid"]


            # Function to fetch username using UID from the 'usernames' table
            def fetch_username(uid):
                try:
                    response = supabase.table("usernames").select("username").eq("UID", uid).execute()
                    if response.data:
                        return response.data[0]["username"]
                    else:
                        st.error("Username not found for the given UID.")
                        return None
                except Exception as e:
                    st.error(f"An error occurred while fetching username: {e}")
                    return None


            # Fetch the username
            username = fetch_username(user_uid)

            if username:
                st.write(f"Welcome back, **{username}**! Let's crush your exams!")
            else:
                st.write(f"Welcome back, **{st.session_state['user_name']}**! Let's crush your exams!")
        else:
            st.error("User UID is not found in session state.")

        user_email = st.session_state["user_name"]

        # Fetch tasks - This triggers the update each time the page is accessed
        upcoming_tasks = fetch_upcoming_tasks(user_email)
        todays_tasks = fetch_todays_tasks(user_email)
        total_tasks, completed_tasks, progress_percentage = fetch_task_progress(user_email)

        # Dashboard Cards with dynamic data
        col1, col2, col3 = st.columns(3)

        with col1:
            # Upcoming Exams/Projects Metric
            upcoming_count = len(upcoming_tasks)
            upcoming_days_left = len(
                [task for task in upcoming_tasks if task['date'] > datetime.now().strftime('%Y-%m-%d')])
            st.metric("Upcoming Exams/Projects", str(upcoming_count), f"{upcoming_days_left} Days Left")

        with col2:
            # Today's Study Schedule Metric
            todays_count = len(todays_tasks)
            st.metric("Today's Study Schedule", str(todays_count), "On Track" if todays_count > 0 else "No Tasks")

        with col3:
            # Overall Progress Metric
            st.metric("Overall Progress", f"{progress_percentage:.2f}%",
                      f"{completed_tasks} of {total_tasks} tasks completed")

        # Upload Syllabus Section
        st.markdown("### Upload or Copy-Paste Your Syllabus")
        col1, col2 = st.columns(2)

        with col1:
            uploaded_file = st.file_uploader("Upload File")

        with col2:
            syllabus_text = st.text_area("Paste Syllabus Here")

        # Option to Select Days Left
        days_left = st.number_input(
            "Enter the number of days left until your exams",
            min_value=1,
            value=5,
            step=1
        )

        if uploaded_file:
            from PyPDF2 import PdfReader

            reader = PdfReader(uploaded_file)
            syllabus_text = ""
            for page in reader.pages:
                syllabus_text += page.extract_text()

        # Generate Study Plan Button
        if st.button("Generate Study Plan"):
            if not syllabus_text.strip():
                st.error("Please upload a syllabus file or paste the syllabus text.")
            else:
                try:
                    # Step 1: Generate topics and subtopics
                    main_topics, subtopics_by_topic = topics_checklist(syllabus_text)

                    if main_topics:
                        st.markdown("### Interactive Checklist")
                        
                        # Use session state to preserve checkbox states
                        if "checklist_state" not in st.session_state:
                            st.session_state.checklist_state = {}

                        # Start a form
                        with st.form("checklist_form"):
                            for main_topic, subtopics in subtopics_by_topic.items():
                                st.markdown(f"#### {main_topic}")
                                for idx, subtopic in enumerate(subtopics):  # Add index for uniqueness
                                    key = f"{main_topic}_{subtopic}_{idx}"  # Combine topic, subtopic, and index
                                    
                                    # Initialize the checkbox state if not already set
                                    if key not in st.session_state.checklist_state:
                                        st.session_state.checklist_state[key] = False
                                    
                                    # Render the checkbox
                                    checked = st.checkbox(
                                        subtopic, key=key, value=st.session_state.checklist_state[key]
                                    )
                                    
                                    # Update session state
                                    st.session_state.checklist_state[key] = checked

                                    # Display the subtopic with strikethrough if checked
                                    if checked:
                                        st.markdown(f"<s>{subtopic}</s>", unsafe_allow_html=True)
                            
                            # Submit button
                            submitted = st.form_submit_button("Submit")

                        # Update checklist state only after submission
                        if submitted:
                            st.success("Checklist updated!")
                            st.write("Checklist State:")
                            st.write(st.session_state.checklist_state)
                    else:
                        st.error("Could not generate topics and subtopics.")

                except Exception as e:
                    st.error(f"An error occurred: {e}")

        # Step 2: Generate a day-wise study plan
        try:
            study_plan = generate_study_plan(syllabus_text, days_left)
            st.success("Study Plan Generated Successfully!")
            st.markdown("### Day-Wise Study Plan")
            text = study_plan
            # Create a placeholder to dynamically update the content
            placeholder = st.empty()
            typing_speed=0.005

            # Start typing animation
            displayed_text = ""
            for char in text:
                displayed_text += char
                placeholder.markdown(f"**{displayed_text}**")  # You can style it as needed
                time.sleep(typing_speed)

            # Ensure the final text is displayed
            placeholder.markdown(f"**{text}**")
        except Exception as e:
            st.error(f"Error generating study plan: {e}")

            # Create a placeholder to dynamically update the content
    placeholder = st.empty()


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
    settings()

elif selection == "Logout":
    logout()