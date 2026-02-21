# main.py
import os
import uuid
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import boto3
import torch
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Polyvox API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Global model - load once
converter = None
polly = None


def get_converter():
    global converter
    if converter is None:
        from OpenVoice.openvoice.api import ToneColorConverter

        print("Loading OpenVoice model...")
        converter = ToneColorConverter(
            "checkpoints_v2/converter/config.json", device="cpu"
        )
        converter.load_ckpt("checkpoints_v2/converter/checkpoint.pth")
        print("OpenVoice loaded!")
    return converter


def get_polly():
    global polly
    if polly is None:
        polly = boto3.client("polly", region_name="us-east-1")
    return polly


# In-memory store for speaker embeddings
speaker_embeddings = {}


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/enroll")
async def enroll(user_id: str = Form(...), audio: UploadFile = File(...)):
    """Upload a voice sample and extract speaker embedding."""
    file_ext = Path(audio.filename).suffix or ".wav"
    raw_path = UPLOAD_DIR / f"{user_id}_raw{file_ext}"
    wav_path = UPLOAD_DIR / f"{user_id}.wav"

    with open(raw_path, "wb") as f:
        f.write(await audio.read())

    # Convert to wav if needed
    if file_ext.lower() != ".wav":
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_path),
                "-ar",
                "22050",
                "-ac",
                "1",
                str(wav_path),
            ],
            capture_output=True,
        )
    else:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_path),
                "-ar",
                "22050",
                "-ac",
                "1",
                str(wav_path),
            ],
            capture_output=True,
        )

    # Extract speaker embedding
    conv = get_converter()
    se = conv.extract_se(str(wav_path))
    speaker_embeddings[user_id] = se

    return {"status": "enrolled", "user_id": user_id}


@app.post("/synthesize")
async def synthesize(user_id: str = Form(...), text: str = Form(...)):
    """Generate SA-accented speech in user's voice."""
    if user_id not in speaker_embeddings:
        raise HTTPException(
            status_code=404, detail="User not enrolled. Call /enroll first."
        )

    target_se = speaker_embeddings[user_id]
    output_id = str(uuid.uuid4())[:8]

    # 1. Generate SA accent with Polly
    polly_client = get_polly()
    response = polly_client.synthesize_speech(
        Text=text, OutputFormat="mp3", VoiceId="Ayanda", Engine="neural"
    )

    polly_mp3 = OUTPUT_DIR / f"{output_id}_polly.mp3"
    polly_wav = OUTPUT_DIR / f"{output_id}_polly.wav"

    with open(polly_mp3, "wb") as f:
        f.write(response["AudioStream"].read())

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(polly_mp3),
            "-ar",
            "22050",
            "-ac",
            "1",
            str(polly_wav),
        ],
        capture_output=True,
    )

    # 2. Extract Polly SE and convert
    conv = get_converter()
    source_se = conv.extract_se(str(polly_wav))

    output_path = OUTPUT_DIR / f"{output_id}_output.wav"
    conv.convert(
        audio_src_path=str(polly_wav),
        src_se=source_se,
        tgt_se=target_se,
        output_path=str(output_path),
    )

    return {"status": "success", "audio_url": f"/audio/{output_id}_output.wav"}


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve generated audio files."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(file_path, media_type="audio/wav")
