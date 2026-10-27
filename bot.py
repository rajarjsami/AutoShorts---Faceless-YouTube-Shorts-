#!/usr/bin/env python3
"""
Faceless YouTube Shorts Automation Engine
==========================================
Generates, renders, and publishes 1080x1920 vertical YouTube Shorts daily via GitHub Actions.

Pipeline:
1. Google Generative AI (Gemini): Generates viral 40s script (title, description, voiceover).
2. Microsoft Edge TTS: Synthesizes high-fidelity voiceover MP3.
3. Pexels API: Fetches vertical HD background footage matching the niche.
4. MoviePy (1.0.3): Loops video to match audio length, formats 9:16 1080x1920, and merges audio.
5. Google API Python Client: Resumable OAuth upload to YouTube Shorts.
"""

import os
import sys
import json
import re
import random
import asyncio
import requests
from dotenv import load_dotenv

# 1. AI Script Generation
import google.generativeai as genai

# 2. Text-to-Speech
import edge_tts

# 3. Video Editing (MoviePy 1.0.3)
from moviepy.editor import VideoFileClip, AudioFileClip, vfx

# 4. YouTube Data API v3
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# Load local environment if present (.env)
load_dotenv()

# Configuration & Constants
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")  # public, unlisted, or private
SHORTS_NICHE = os.getenv("SHORTS_NICHE", "")

# Output Artifact Paths
AUDIO_OUTPUT = "voiceover.mp3"
BACKGROUND_VIDEO_OUTPUT = "background.mp4"
FINAL_VIDEO_OUTPUT = "final_short.mp4"
TOKEN_FILE = "token.json"

# Curated high-engagement niches for daily rotation
VIRAL_NICHES = [
    "mind-bending psychology facts about human behavior",
    "fascinating mysteries of the deep ocean and cosmic space",
    "ancient historical facts that sound fake but are 100% true",
    "stoic life principles and dark psychology for mental strength",
    "bizarre scientific phenomena that scientists still cannot explain",
    "unbelievable survival stories and extreme human resilience",
    "futuristic technology trends and artificial intelligence breakthroughs"
]

DEFAULT_VOICE = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")  # Deep, documentary-style narrator


def validate_environment():
    """Verify required API credentials before executing the pipeline."""
    missing = []
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not PEXELS_API_KEY:
        missing.append("PEXELS_API_KEY")
    if not YOUTUBE_CLIENT_SECRET and not os.path.exists(TOKEN_FILE):
        missing.append("YOUTUBE_CLIENT_SECRET (or token.json)")

    if missing:
        print(f"[FATAL] Missing required credentials: {', '.join(missing)}")
        print("Please configure them in your environment or GitHub Secrets.")
        sys.exit(1)


# ==============================================================================
# STEP 1: Gemini AI Script Generation (Strict JSON)
# ==============================================================================
def generate_script(niche: str = "") -> dict:
    """
    Calls Google Gemini to generate a strict JSON script tailored for a 40-second Short.
    Returns: dict with 'title', 'description', 'voiceover_text', and 'background_query'.
    """
    print("\n--- Step 1: Generating Short Script with Gemini AI ---")
    genai.configure(api_key=GEMINI_API_KEY)

    selected_niche = niche.strip() if niche else random.choice(VIRAL_NICHES)
    print(f"Selected Niche: {selected_niche}")

    # A 40-second voiceover at 2.5 words/sec requires approximately 95-105 words.
    system_prompt = (
        "You are an elite YouTube Shorts creator producing high-retention faceless shorts. "
        "Create an intriguing, fast-paced script designed for exactly 40 seconds of speaking time. "
        "Strict rules for voiceover_text:\n"
        "- Exactly 95 to 110 spoken words.\n"
        "- Hook the viewer in the first 3 seconds with a shocking statement or question.\n"
        "- Fast narrative momentum, vivid storytelling, strong cliffhanger/payoff.\n"
        "- Do NOT include bracketed directions like [Music], [Pause], [SFX], or 'Narrator:'.\n"
        "- Only clean, speakable prose with natural punctuation.\n\n"
        "Return ONLY a valid, raw JSON object with the following exact keys:\n"
        "{\n"
        '  "title": "Short title with high CTR under 60 characters including #Shorts",\n'
        '  "description": "Engaging 2-3 sentence description with #Shorts #Facts #Viral",\n'
        '  "voiceover_text": "Complete spoken narrative without tags (95-110 words)",\n'
        '  "background_query": "2-word search term for vertical footage (e.g. \'dark ocean\', \'galaxy space\', \'storm clouds\')"\n'
        "}"
    )

    user_prompt = f"Topic/Niche: {selected_niche}. Generate the complete 40-second Short."

    # Using recommended fast model
    model = genai.GenerativeModel("gemini-pro")

    try:
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config={"temperature": 0.85, "top_p": 0.95}
        )
        raw_text = response.text.strip()
    except Exception as e:
        print(f"[ERROR] Gemini API request failed: {e}")
        model_fallback = genai.GenerativeModel("gemini-pro")
        response = model_fallback.generate_content(f"{system_prompt}\n\n{user_prompt}")
        raw_text = response.text.strip()

    # Strip code fences if returned by model
    clean_json_str = raw_text
    if clean_json_str.startswith("```"):
        clean_json_str = re.sub(r"^```(?:json)?\n?", "", clean_json_str)
        clean_json_str = re.sub(r"\n?```$", "", clean_json_str)

    try:
        script_data = json.loads(clean_json_str)
    except json.JSONDecodeError as err:
        print(f"[WARN] Direct JSON decode failed: {err}. Attempting regex extraction.")
        match = re.search(r"\{.*\}", clean_json_str, re.DOTALL)
        if match:
            script_data = json.loads(match.group(0))
        else:
            raise ValueError(f"Could not parse valid JSON from Gemini output: {raw_text}")

    # Verify required keys
    for required_key in ["title", "description", "voiceover_text"]:
        if required_key not in script_data or not script_data[required_key]:
            raise KeyError(f"Missing required key in AI response: '{required_key}'")

    if "#Shorts" not in script_data["title"] and "#shorts" not in script_data["title"]:
        script_data["title"] = f"{script_data['title']} #Shorts"
    if "#Shorts" not in script_data["description"]:
        script_data["description"] = f"{script_data['description']}\n\n#Shorts #Viral"

    if "background_query" not in script_data:
        script_data["background_query"] = "space galaxy"

    word_count = len(script_data["voiceover_text"].split())
    print(f"Title: {script_data['title']}")
    print(f"Voiceover length: {word_count} words (~{word_count / 2.5:.1f}s estimated)")
    print(f"Background footage query: {script_data['background_query']}")

    return script_data


# ==============================================================================
# STEP 2: Edge-TTS Audio Voiceover Synthesis
# ==============================================================================
async def synthesize_speech_async(text: str, output_path: str, voice: str = DEFAULT_VOICE):
    """Synthesizes high-fidelity voiceover using edge-tts."""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+0%", volume="+0%")
    await communicate.save(output_path)


def generate_audio(text: str, output_path: str = AUDIO_OUTPUT) -> str:
    """Generates MP3 audio file from script text."""
    print(f"\n--- Step 2: Synthesizing Voiceover with Edge-TTS ({DEFAULT_VOICE}) ---")
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass

    asyncio.run(synthesize_speech_async(text, output_path))

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Edge-TTS failed to produce an audio file.")

    print(f"Voiceover saved successfully to '{output_path}' ({os.path.getsize(output_path)} bytes)")
    return output_path


# ==============================================================================
# STEP 3: Pexels API Vertical HD Video Fetch
# ==============================================================================
def download_pexels_vertical_video(query: str, output_path: str = BACKGROUND_VIDEO_OUTPUT) -> str:
    """
    Searches Pexels for a vertical (9:16) portrait HD video and downloads the best quality stream.
    """
    print(f"\n--- Step 3: Fetching Vertical HD Background Video from Pexels ('{query}') ---")
    headers = {"Authorization": PEXELS_API_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {
        "query": query,
        "orientation": "portrait",
        "per_page": 15,
        "size": "medium"
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)
    if response.status_code != 200:
        print(f"[WARN] Pexels query '{query}' failed with status {response.status_code}. Fallback to 'cinematic nature'.")
        params["query"] = "cinematic nature"
        response = requests.get(url, headers=headers, params=params, timeout=20)

    response.raise_for_status()
    data = response.json()
    videos = data.get("videos", [])

    if not videos:
        raise RuntimeError(f"No vertical background videos found on Pexels for query: {query}")

    chosen_video = random.choice(videos[:5])
    video_files = chosen_video.get("video_files", [])

    portrait_files = [
        f for f in video_files
        if f.get("height", 0) > f.get("width", 0) and f.get("link")
    ]

    if not portrait_files:
        portrait_files = sorted(video_files, key=lambda x: x.get("height", 0), reverse=True)

    best_file = max(portrait_files, key=lambda x: x.get("height", 0))
    download_url = best_file["link"]
    print(f"Selected Pexels Video ID: {chosen_video.get('id')} ({best_file.get('width')}x{best_file.get('height')})")

    print(f"Downloading stream into '{output_path}'...")
    with requests.get(download_url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    print(f"Background video downloaded ({os.path.getsize(output_path)} bytes)")
    return output_path


# ==============================================================================
# STEP 4: MoviePy (1.0.3) Audio/Video Merge & 9:16 Format
# ==============================================================================
def create_short_video(
    audio_path: str = AUDIO_OUTPUT,
    video_path: str = BACKGROUND_VIDEO_OUTPUT,
    output_path: str = FINAL_VIDEO_OUTPUT
) -> str:
    """
    Uses moviepy==1.0.3 to:
    - Loop background video if duration is shorter than voiceover.
    - Trim to exact audio length.
    - Resize and crop to 1080x1920 (vertical 9:16 ratio).
    - Merge audio track and export rendered MP4.
    """
    print("\n--- Step 4: Merging Audio and Video with MoviePy (1.0.3) ---")

    audio_clip = AudioFileClip(audio_path)
    audio_duration = audio_clip.duration
    print(f"Voiceover Audio Duration: {audio_duration:.2f} seconds")

    video_clip = VideoFileClip(video_path)
    print(f"Raw Background Duration: {video_clip.duration:.2f}s | Resolution: {video_clip.w}x{video_clip.h}")

    if video_clip.duration < audio_duration:
        print(f"Looping video to match audio duration ({audio_duration:.2f}s)...")
        video_clip = vfx.loop(video_clip, duration=audio_duration)
    else:
        video_clip = video_clip.subclip(0, audio_duration)

    target_w, target_h = 1080, 1920
    current_ratio = video_clip.w / video_clip.h
    target_ratio = target_w / target_h

    if current_ratio > target_ratio:
        scaled_clip = video_clip.resize(height=target_h)
        x_center = scaled_clip.w / 2
        final_video = scaled_clip.crop(x1=x_center - target_w / 2, y1=0, x2=x_center + target_w / 2, y2=target_h)
    else:
        scaled_clip = video_clip.resize(width=target_w)
        y_center = scaled_clip.h / 2
        final_video = scaled_clip.crop(x1=0, y1=y_center - target_h / 2, x2=target_w, y2=y_center + target_h / 2)

    final_video = final_video.set_audio(audio_clip)
    final_video = final_video.set_duration(audio_duration)

    print(f"Rendering final short ({target_w}x{target_h} @ 30fps) to '{output_path}'...")
    final_video.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        logger=None
    )

    audio_clip.close()
    video_clip.close()
    final_video.close()

    print(f"Final Short successfully exported: '{output_path}' ({os.path.getsize(output_path)} bytes)")
    return output_path


# ==============================================================================
# STEP 5: Google API Python Client YouTube Upload
# ==============================================================================
def get_youtube_credentials() -> Credentials:
    """
    Resolves YouTube OAuth 2.0 credentials in both local and headless CI environments.
    """
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None

    if YOUTUBE_CLIENT_SECRET:
        try:
            secret_data = json.loads(YOUTUBE_CLIENT_SECRET)
            if "refresh_token" in secret_data:
                print("Authenticated via YOUTUBE_CLIENT_SECRET (Authorized User Refresh Token)")
                creds = Credentials.from_authorized_user_info(secret_data, SCOPES)
            elif "installed" in secret_data or "web" in secret_data:
                with open("client_secret.json", "w") as f:
                    json.dump(secret_data, f)
        except json.JSONDecodeError:
            pass

    if not creds and os.path.exists(TOKEN_FILE):
        print(f"Loading credentials from '{TOKEN_FILE}'...")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        print("Credentials expired. Refreshing OAuth token via Google Auth transport...")
        creds.refresh(Request())
        try:
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
        except Exception:
            pass

    if not creds or not creds.valid:
        client_secret_file = "client_secret.json"
        if not os.path.exists(client_secret_file) and not YOUTUBE_CLIENT_SECRET:
            raise RuntimeError(
                "YouTube credentials not found. Please provide YOUTUBE_CLIENT_SECRET "
                "or run setup_oauth.py locally to generate token.json."
            )

        print("[LOCAL FLOW] Starting local OAuth browser flow...")
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
        creds = flow.run_local_server(port=8080)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        print(f"Saved refreshed credentials to '{TOKEN_FILE}'")

    return creds


def upload_to_youtube(video_path: str, title: str, description: str, privacy: str = YOUTUBE_PRIVACY_STATUS) -> str:
    """Uploads the rendered vertical MP4 as a YouTube Short."""
    print("\n--- Step 5: Uploading Final MP4 to YouTube Shorts ---")
    creds = get_youtube_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": ["Shorts", "Facts", "Viral", "DidYouKnow", "DailyShorts"],
            "categoryId": "27"
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        video_path,
        chunksize=1024 * 1024 * 4,
        resumable=True,
        mimetype="video/mp4"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    print(f"Uploading '{video_path}' (Privacy: {privacy})...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"Upload progress: {progress}%")

    video_id = response.get("id")
    short_url = f"https://youtube.com/shorts/{video_id}"
    print(f"\n=======================================================")
    print(f"[SUCCESS] YouTube Short Uploaded Successfully!")
    print(f"Video ID  : {video_id}")
    print(f"Short URL : {short_url}")
    print(f"Title     : {title}")
    print(f"Privacy   : {privacy}")
    print(f"=======================================================\n")
    return short_url


def main():
    print("=======================================================")
    print("      FACELESS YOUTUBE SHORTS AUTOMATION BOT           ")
    print("=======================================================")
    validate_environment()

    # 1. Script Generation
    script_data = generate_script(niche=SHORTS_NICHE)

    # 2. TTS Voiceover
    audio_path = generate_audio(script_data["voiceover_text"])

    # 3. Pexels Background Footage
    video_path = download_pexels_vertical_video(script_data["background_query"])

    # 4. MoviePy Video Composition
    final_video = create_short_video(audio_path=audio_path, video_path=video_path)

    # 5. YouTube API Upload
    upload_url = upload_to_youtube(
        video_path=final_video,
        title=script_data["title"],
        description=script_data["description"]
    )

    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"video_url={upload_url}\n")
            f.write(f"video_title={script_data['title']}\n")

    print("[PIPELINE COMPLETE] Job finished successfully.")


if __name__ == "__main__":
    main()
