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
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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

# Voice registry: Polly neural voices (Phase 1). OpenVoice base speakers in Phase 2.
POLLY_VOICES = [
    {"id": "Ayanda", "name": "Ayanda (South African)", "engine": "neural"},
    {"id": "Nicole", "name": "Nicole (Australian)", "engine": "neural"},
    {"id": "Olivia", "name": "Olivia (Australian)", "engine": "neural"},
    {"id": "Russell", "name": "Russell (Australian)", "engine": "neural"},
    {"id": "Amy", "name": "Amy (British)", "engine": "neural"},
    {"id": "Emma", "name": "Emma (British)", "engine": "neural"},
    {"id": "Brian", "name": "Brian (British)", "engine": "neural"},
    {"id": "Arthur", "name": "Arthur (British)", "engine": "neural"},
    {"id": "Joanna", "name": "Joanna (US)", "engine": "neural"},
    {"id": "Matthew", "name": "Matthew (US)", "engine": "neural"},
    {"id": "Ruth", "name": "Ruth (US)", "engine": "neural"},
    {"id": "Stephen", "name": "Stephen (US)", "engine": "neural"},
    {"id": "Danielle", "name": "Danielle (US)", "engine": "neural"},
    {"id": "Gregory", "name": "Gregory (US)", "engine": "neural"},
    {"id": "Niamh", "name": "Niamh (Irish)", "engine": "neural"},
    {"id": "Aria", "name": "Aria (New Zealand)", "engine": "neural"},
    {"id": "Kajal", "name": "Kajal (Indian)", "engine": "neural"},
]
POLLY_VOICE_IDS = {v["id"] for v in POLLY_VOICES}


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/voices")
async def list_voices():
    """Return available base voices (Polly + OpenVoice base speakers if present)."""
    voices = [
        {"id": v["id"], "name": v["name"], "source": "polly"}
        for v in POLLY_VOICES
    ]
    # Phase 2: scan checkpoints_v2/base_speakers/ses/*.pth if folder exists
    base_speakers_dir = Path("checkpoints_v2/base_speakers/ses")
    if base_speakers_dir.exists():
        for pth in base_speakers_dir.glob("*.pth"):
            voice_id = pth.stem
            voices.append({
                "id": voice_id,
                "name": voice_id.replace("-", " ").title(),
                "source": "openvoice",
            })
    return {"voices": voices}


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


# Default voice sample for unenrolled users (optional). If present, used as target.
SAMPLES_DIR = Path("samples")
DEFAULT_VOICE_PATH = SAMPLES_DIR / "default_voice.wav"
default_speaker_embedding = None


def get_default_speaker_embedding():
    """Load default voice embedding from samples/default_voice.wav if it exists."""
    global default_speaker_embedding
    if default_speaker_embedding is not None:
        return default_speaker_embedding
    if DEFAULT_VOICE_PATH.exists():
        conv = get_converter()
        default_speaker_embedding = conv.extract_se(str(DEFAULT_VOICE_PATH))
    return default_speaker_embedding


@app.post("/synthesize")
async def synthesize(
    user_id: str = Form(...),
    text: str = Form(...),
    voice_id: str = Form("Ayanda"),
):
    """Generate speech. Uses user's voice if enrolled, else default voice or raw Polly."""
    # Validate voice_id against allowed Polly voices (Phase 1)
    if voice_id not in POLLY_VOICE_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice_id. Must be one of: {sorted(POLLY_VOICE_IDS)}",
        )

    # Resolve target: enrolled user > default sample > None (skip conversion)
    target_se = None
    if user_id in speaker_embeddings:
        target_se = speaker_embeddings[user_id]
    else:
        target_se = get_default_speaker_embedding()

    output_id = str(uuid.uuid4())[:8]

    # Resolve engine for this voice
    voice_info = next((v for v in POLLY_VOICES if v["id"] == voice_id), None)
    engine = voice_info["engine"] if voice_info else "neural"

    # 1. Generate base audio with Polly
    polly_client = get_polly()
    response = polly_client.synthesize_speech(
        Text=text, OutputFormat="mp3", VoiceId=voice_id, Engine=engine
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

    # 2. Convert to target voice if we have one, else use Polly output as-is
    if target_se is not None:
        conv = get_converter()
        source_se = conv.extract_se(str(polly_wav))
        output_path = OUTPUT_DIR / f"{output_id}_output.wav"
        conv.convert(
            audio_src_path=str(polly_wav),
            src_se=source_se,
            tgt_se=target_se,
            output_path=str(output_path),
        )
        return {
            "status": "success",
            "audio_url": f"/audio/{output_id}_output.wav",
            "original_audio_url": f"/audio/{output_id}_polly.wav",
        }
    else:
        # No enrollment, no default sample: return Polly output directly
        return {
            "status": "success",
            "audio_url": f"/audio/{output_id}_polly.wav",
            "original_audio_url": f"/audio/{output_id}_polly.wav",
        }


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve generated audio files."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(file_path, media_type="audio/wav")
