# ⚙️ Installation Guide

Step-by-step instructions for running locally or deploying to Vercel.

## Prerequisites

- [Python](https://www.python.org/downloads/) 3.9+
- [Git](https://git-scm.com/downloads/)
- A **Groq API key** – get one free at [console.groq.com](https://console.groq.com)

---

## 1. Clone the Repository

```bash
git clone https://github.com/1MaNan071/Customer-Support-Agent.git
cd Customer-Support-Agent
```

---

## 2. Create and Activate a Virtual Environment

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
.\venv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and replace the placeholder with your real Groq API key:

```
GROQ_API_KEY="gsk_YourSecretKeyGoesHere"
```

---

## 5. (Optional) Add Your Own FAQ Data

Edit `faq_data.json` with your company's questions and answers, **or** upload a file through the UI after starting the server.

---

## 6. Run the Application

```bash
uvicorn api.index:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

---

## 7. Deploy to Vercel

1. Push the repo to GitHub.
2. Import it at [vercel.com/new](https://vercel.com/new).
3. Add `GROQ_API_KEY` as an environment variable.
4. Click **Deploy**.
