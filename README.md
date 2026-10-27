# AutoShorts: Faceless YouTube Shorts Automation Engine

A fully automated, production-grade pipeline built to generate, voice, compose, and upload vertical (1080x1920) YouTube Shorts every single day using standard GitHub Actions runners. Zero Docker, zero Ollama, zero local server requirements.

---

## 🛠 Architecture & Tech Stack

| Step | Component | Technology / Library | Purpose |
| :--- | :--- | :--- | :--- |
| **1. Scriptwriting** | Google Gemini AI | `google-generativeai` | Generates strict JSON script (`title`, `description`, `voiceover_text`) tuned for high viewer retention |
| **2. Voiceover** | Microsoft Edge TTS | `edge-tts` | Free, neural, human-grade voice synthesis outputting high-bitrate MP3 |
| **3. Visuals** | Pexels Video API | `requests` | Fetches vertical (9:16) HD cinematic footage aligned with the video theme |
| **4. Editing** | MoviePy | `moviepy==1.0.3` | Trims, loops video, crops to 1080x1920, and merges audio track |
| **5. Publishing** | YouTube Data API v3 | `google-api-python-client` | Resumable chunked upload with automated `#Shorts` classification |
| **6. CI/CD Orchestration** | GitHub Actions | `ubuntu-latest` | Runs daily via cron with FFmpeg & Python 3.10 |

---

## 📁 Repository Structure

```text
├── .github/
│   └── workflows/
│       └── auto-run.yml        # Daily cron schedule and manual workflow dispatch
├── bot.py                      # Master automation pipeline
├── requirements.txt            # Python dependencies (moviepy==1.0.3 pinned)
├── setup_oauth.py              # 1-time local helper to generate YouTube OAuth refresh token
└── README.md                   # Complete documentation & secrets guide
```

---

## 🔑 GitHub Secrets Configuration

Before enabling the workflow, add these 3 repository secrets in **GitHub -> Settings -> Secrets and variables -> Actions**:

| Secret Name | Description | How to obtain |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API Key | Get from [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `PEXELS_API_KEY` | Pexels Stock Video API Key | Free registration at [Pexels API](https://www.pexels.com/api/) |
| `YOUTUBE_CLIENT_SECRET` | OAuth 2.0 Credentials / Refresh Token | Run `python setup_oauth.py` once locally (see below) |
