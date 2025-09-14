# ⚙️ Installation Guide

This guide provides step-by-step instructions to set up and run the LangGraph Customer Support Assistant on your local machine.

## Prerequisites

- [Python](https://www.python.org/downloads/) 3.9 or higher
- [Git](https://git-scm.com/downloads/) installed on your system

---

## 1. Clone the Repository

Clone the project repository from GitHub to your local machine:

```bash
git clone https://github.com/1MaNan071/Customer-Support-Agent.git
cd Customer-Support-Agent
```

---

## 2. Create and Activate a Virtual Environment

Use a virtual environment to manage project dependencies and avoid conflicts with other Python projects.

### On macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### On Windows:

```bash
python -m venv venv
.\venv\Scripts\activate
```

*You will know the environment is active when you see `(venv)` at the beginning of your terminal prompt.*

---

## 3. Install Dependencies

With your virtual environment active, install all the required Python libraries:

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

The application requires an API key from Groq to function.

1. Locate the `.env.example` file in the project's root directory.
2. Create a copy of this file and rename it to `.env`.
3. Open the new `.env` file and replace `"your-key-here"` with your actual Groq API key.

Your `.env` file should look like this:

```
# This is an example file.
# Create a new file named .env and add your Groq API key there.
GROQ_API_KEY="gsk_YourSecretKeyGoesHere"
```

*The `.env` file is listed in `.gitignore`, so your secret key will never be committed to the repository.*

---

## 5. Run the Application

Once all the steps above are completed, you can run the Streamlit application:

```bash
streamlit run app.py
```

Your web browser should automatically open a new tab with the chat assistant running.  
If not, your terminal will show a local URL (usually `http://localhost:8501`) that you can open manually.
