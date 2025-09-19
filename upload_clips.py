import os
import sys
import subprocess
import requests
import random
import shutil
import logging
import time  # <-- Added time for sleep delay
from instagrapi import Client
from dotenv import load_dotenv

# ============================================
# LOGGING CONFIGURATION
# ============================================
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
)

# File handler → logs to upload_log.txt
file_handler = logging.FileHandler("upload_log.txt", encoding="utf-8")
file_handler.setFormatter(log_formatter)

# Console handler → logs to stdout
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================

load_dotenv()  # Load variables from .env file

# ✅ Upload toggles
UPLOAD_TO_TIKTOK = True
UPLOAD_TO_INSTAGRAM = True

# ✅ Upload Controls
MAX_TIKTOK_UPLOADS = 10  # Daily limit for TikTok uploads
MIN_DELAY = 60  # Minimum wait time between uploads (seconds)
MAX_DELAY = 180  # Maximum wait time between uploads (seconds)

# ✅ TikTok API credentials (loaded from .env)
CLIENT_KEY = os.getenv("CLIENT_KEY")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# ✅ Instagram credentials (loaded from .env)
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

# ✅ Folder paths
FOLDER_CLIPS_READY = r"D:\Santiago Marin\Clips\Clips_ready_to_upload"
FOLDER_PROCESSED = r"D:\Santiago Marin\Clips\Processed_Clips"

# ✅ TikTok API endpoints and Captions file
UPLOAD_ENDPOINT = "https://open.tiktokapis.com/v2/video/upload/"
PUBLISH_ENDPOINT = "https://open.tiktokapis.com/v2/video/publish/"
CAPTIONS_FILE = "captions.txt"
SESSION_FILE = "ig_session.json"  # Cache Instagram session


# ============================================
# HELPERS
# ============================================


def load_captions():
    """Load captions from captions.txt"""
    if not os.path.exists(CAPTIONS_FILE):
        logger.warning("captions.txt not found. Using default caption.")
        return ["Uploaded via API"]
    with open(CAPTIONS_FILE, "r", encoding="utf-8") as f:
        captions = [line.strip() for line in f if line.strip()]
    return captions if captions else ["Uploaded via API"]


def convert_webm_to_mp4(file_path):
    """Convert .webm → .mp4 using ffmpeg"""
    # Create the output path in the same directory as the source
    output_folder = os.path.dirname(file_path)
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    mp4_path = os.path.join(output_folder, f"{base_filename}_converted.mp4")

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", file_path, mp4_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        logger.info(
            f"🔄 Converted {os.path.basename(file_path)} → {os.path.basename(mp4_path)}"
        )
        return mp4_path
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to convert {file_path}. Error: {e}")
        return None


def upload_to_tiktok(file_path, caption):
    """Upload a video to TikTok (Draft by default)"""
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    with open(file_path, "rb") as f:
        files = {"video": (os.path.basename(file_path), f, "video/mp4")}
        response = requests.post(UPLOAD_ENDPOINT, headers=headers, files=files)

    if response.status_code != 200:
        logger.error(f"❌ TikTok upload failed: {response.text}")
        return False

    upload_data = response.json()
    video_id = upload_data.get("data", {}).get("video_id")

    if not video_id:
        logger.error("❌ No TikTok video_id returned")
        return False

    publish_body = {
        "video_id": video_id,
        "post_info": {
            "title": caption,
            "privacy_level": "SELF",  # Draft
        },
    }

    publish_response = requests.post(
        PUBLISH_ENDPOINT, headers=headers, json=publish_body
    )

    if publish_response.status_code == 200:
        logger.info(f"✅ TikTok upload success: {os.path.basename(file_path)}")
        return True
    else:
        logger.error(f"❌ TikTok publish failed: {publish_response.text}")
        return False


def get_instagram_client():
    """Login to Instagram once and cache session"""
    cl = Client()

    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USERNAME, IG_PASSWORD)
            logger.info("✅ Instagram session loaded from cache.")
            return cl
        except Exception as e:
            logger.warning(f"⚠️ Failed to load cached Instagram session: {e}")

    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        logger.info("✅ Instagram login successful (new session cached).")
        return cl
    except Exception as e:
        logger.error(f"❌ Could not log into Instagram: {e}")
        return None


def upload_to_instagram(cl, file_path, caption):
    """Upload a video to Instagram Reels"""
    try:
        cl.clip_upload(file_path, caption=caption)
        logger.info(f"✅ Instagram upload success: {os.path.basename(file_path)}")
        return True
    except Exception as e:
        logger.error(f"❌ Instagram upload failed: {e}")
        return False


# ============================================
# MAIN SCRIPT
# ============================================


def main():
    # Ensure necessary folders exist
    os.makedirs(FOLDER_PROCESSED, exist_ok=True)

    captions = load_captions()
    clips_to_process = [
        f
        for f in os.listdir(FOLDER_CLIPS_READY)
        if f.lower().endswith((".mp4", ".webm"))
    ]

    if not clips_to_process:
        logger.warning("⚠️ No new clips found in the folder.")
        return

    logger.info(f"📹 Found {len(clips_to_process)} clips. Starting upload...\n")

    ig_client = get_instagram_client() if UPLOAD_TO_INSTAGRAM else None
    if UPLOAD_TO_INSTAGRAM and not ig_client:
        logger.warning("⚠️ Instagram login failed. Will skip all Instagram uploads.")

    tiktok_count = 0

    # Create a copy of the list to iterate over, allowing safe removal from the original
    for i, clip_filename in enumerate(list(clips_to_process), start=1):
        # --- Skip already processed files ---
        if os.path.exists(os.path.join(FOLDER_PROCESSED, clip_filename)):
            logger.info(f"⏩ Skipping '{clip_filename}', already in processed folder.")
            continue

        original_clip_path = os.path.join(FOLDER_CLIPS_READY, clip_filename)
        processed_clip_path = original_clip_path

        # Handle WEBM conversion
        if clip_filename.lower().endswith(".webm"):
            processed_clip_path = convert_webm_to_mp4(original_clip_path)
            if not processed_clip_path:
                # Move the problematic webm to processed so we don't try it again
                shutil.move(
                    original_clip_path, os.path.join(FOLDER_PROCESSED, clip_filename)
                )
                continue

        caption = random.choice(captions)
        logger.info(f"\n▶️ Processing {i}/{len(clips_to_process)}: {clip_filename}")
        logger.info(f"📝 Caption: {caption}")

        # --- Track success with flags ---
        tiktok_success = False
        instagram_success = False

        # TikTok Upload
        if UPLOAD_TO_TIKTOK and tiktok_count < MAX_TIKTOK_UPLOADS:
            if upload_to_tiktok(processed_clip_path, caption):
                tiktok_success = True
                tiktok_count += 1
        elif UPLOAD_TO_TIKTOK:
            logger.info("⏳ TikTok daily quota reached. Skipping TikTok for this clip.")

        # Instagram Upload
        if UPLOAD_TO_INSTAGRAM and ig_client:
            if upload_to_instagram(ig_client, processed_clip_path, caption):
                instagram_success = True

        # --- Centralized file movement ---
        if tiktok_success or instagram_success:
            success_platforms = []
            if tiktok_success:
                success_platforms.append("TikTok")
            if instagram_success:
                success_platforms.append("Instagram")
            logger.info(
                f"✅ Successfully uploaded '{clip_filename}' to: {' and '.join(success_platforms)}"
            )
        else:
            logger.warning(f"❌ Upload failed for '{clip_filename}' on all platforms.")

        # Move original source file to processed folder regardless of success to prevent retries
        shutil.move(original_clip_path, os.path.join(FOLDER_PROCESSED, clip_filename))

        # If a .webm was converted to .mp4, clean up the temporary .mp4
        if processed_clip_path != original_clip_path and os.path.exists(
            processed_clip_path
        ):
            os.remove(processed_clip_path)
            logger.info(f"🗑️ Removed temporary mp4 file.")

        # Random delay
        if i < len(clips_to_process):
            delay = random.randint(MIN_DELAY, MAX_DELAY)
            logger.info(f"⏳ Waiting {delay} seconds...")
            time.sleep(delay)

    logger.info("\n🎉 All clips processed!")


if __name__ == "__main__":
    main()
