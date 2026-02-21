# main.py
import json
import logging
import os
import uuid
import subprocess
from pathlib import Path

# #region agent log
def _dbg(loc: str, msg: str, data: dict, hid: str):
    p = Path(__file__).resolve().parent.parent / ".cursor" / "debug-02ba90.log"
    try:
        with open(p, "a") as f:
            f.write(json.dumps({"sessionId": "02ba90", "location": loc, "message": msg, "data": data, "hypothesisId": hid, "timestamp": __import__("time").time() * 1000}) + "\n")
    except Exception:
        pass
# #endregion

log = logging.getLogger(__name__)
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

# OpenVoice base speakers
BASE_SPEAKERS_DIR = Path("checkpoints_v2/base_speakers/ses")
_openvoice_speaker_cache = None
_melotts_import_error = None  # Set when MeloTTS fails to import (e.g. tokenizers version)


def _get_openvoice_voice_ids():
    """Return set of valid OpenVoice voice IDs from base_speakers/ses/."""
    if not BASE_SPEAKERS_DIR.exists():
        return set()
    return {p.stem for p in BASE_SPEAKERS_DIR.glob("*.pth")}


def _get_melotts_speaker(voice_id: str):
    """
    Resolve OpenVoice voice_id to (language, speaker_id) for MeloTTS.
    Returns None if not found.
    """
    global _openvoice_speaker_cache
    if _openvoice_speaker_cache is None:
        _openvoice_speaker_cache = {}
        if not BASE_SPEAKERS_DIR.exists():
            # #region agent log
            _dbg("main.py:_get_melotts_speaker", "BASE_SPEAKERS_DIR missing", {"path": str(BASE_SPEAKERS_DIR)}, "H1")
            # #endregion
            return None
        device = "cuda" if torch.cuda.is_available() else "cpu"
        melo_languages = ["EN_NEWEST", "EN", "ES", "FR", "ZH", "JP", "KR"]
        try:
            from melo.api import TTS
            for lang in melo_languages:
                try:
                    model = TTS(language=lang, device=device)
                    for spk_key, spk_id in model.hps.data.spk2id.items():
                        normalized = spk_key.lower().replace("_", "-")
                        _openvoice_speaker_cache[normalized] = (lang, spk_id)
                    # #region agent log
                    _dbg("main.py:_get_melotts_speaker", "MeloTTS lang loaded", {"lang": lang, "spk2id_keys": list(model.hps.data.spk2id.keys())}, "H3")
                    # #endregion
                except Exception as e:
                    # #region agent log
                    _dbg("main.py:_get_melotts_speaker", "MeloTTS lang failed", {"lang": lang, "error": str(e)}, "H3")
                    # #endregion
                    log.warning("MeloTTS language %s failed: %s", lang, e)
                    continue
            if not _openvoice_speaker_cache:
                log.warning("MeloTTS loaded but no speakers found in spk2id")
            # #region agent log
            _dbg("main.py:_get_melotts_speaker", "Cache built", {"cache_keys": list(_openvoice_speaker_cache.keys()), "cache_len": len(_openvoice_speaker_cache)}, "H2")
            # #endregion
        except ImportError as e:
            global _melotts_import_error
            _melotts_import_error = str(e)
            # #region agent log
            _dbg("main.py:_get_melotts_speaker", "MeloTTS import failed", {"error": str(e)}, "H1")
            # #endregion
            log.warning(
                "MeloTTS not available (run 'make sync-melotts'). ImportError: %s",
                e,
            )
    result = _openvoice_speaker_cache.get(voice_id)
    # #region agent log
    if result is None:
        _dbg("main.py:_get_melotts_speaker", "Voice lookup failed", {"voice_id": voice_id, "cache_keys": list(_openvoice_speaker_cache.keys())}, "H2")
    # #endregion
    return result


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
    """Generate speech. Uses user's voice if enrolled, else default voice or raw output."""
    # Validate voice_id: Polly or OpenVoice base speaker
    openvoice_ids = _get_openvoice_voice_ids()
    if voice_id not in POLLY_VOICE_IDS and voice_id not in openvoice_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice_id. Use a Polly voice or OpenVoice base speaker.",
        )

    # Resolve target: enrolled user > default sample > None (skip conversion)
    target_se = None
    if user_id in speaker_embeddings:
        target_se = speaker_embeddings[user_id]
    else:
        target_se = get_default_speaker_embedding()

    output_id = str(uuid.uuid4())[:8]
    base_wav = OUTPUT_DIR / f"{output_id}_base.wav"

    # 1. Generate base audio: Polly or MeloTTS (OpenVoice)
    if voice_id in POLLY_VOICE_IDS:
        voice_info = next((v for v in POLLY_VOICES if v["id"] == voice_id), None)
        engine = voice_info["engine"] if voice_info else "neural"
        polly_client = get_polly()
        response = polly_client.synthesize_speech(
            Text=text, OutputFormat="mp3", VoiceId=voice_id, Engine=engine
        )
        polly_mp3 = OUTPUT_DIR / f"{output_id}_polly.mp3"
        with open(polly_mp3, "wb") as f:
            f.write(response["AudioStream"].read())
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(polly_mp3), "-ar", "22050", "-ac", "1", str(base_wav)],
            capture_output=True,
        )
    else:
        # OpenVoice base speaker: MeloTTS + pre-computed source_se
        # #region agent log
        _dbg("main.py:synthesize", "OpenVoice path", {"voice_id": voice_id}, "H5")
        # #endregion
        melotts_result = _get_melotts_speaker(voice_id)
        if melotts_result is None:
            hint = ""
            if _melotts_import_error:
                hint = f" Import error: {_melotts_import_error}. Run 'make sync-melotts' to fix."
            raise HTTPException(
                status_code=400,
                detail=f"OpenVoice voice '{voice_id}' not found. MeloTTS may not be installed or base_speakers missing.{hint}",
            )
        language, speaker_id = melotts_result
        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            from melo.api import TTS
            model = TTS(language=language, device=device)
            model.tts_to_file(text, speaker_id, str(base_wav), speed=1.0)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MeloTTS synthesis failed: {e}")

    # 2. Convert to target voice if we have one, else use base as-is
    if target_se is not None:
        conv = get_converter()
        source_se_path = BASE_SPEAKERS_DIR / f"{voice_id}.pth"
        if voice_id in openvoice_ids and source_se_path.exists():
            source_se = torch.load(str(source_se_path), map_location="cpu")
        else:
            # Polly: extract source embedding from generated audio
            source_se = conv.extract_se(str(base_wav))
        output_path = OUTPUT_DIR / f"{output_id}_output.wav"
        conv.convert(
            audio_src_path=str(base_wav),
            src_se=source_se,
            tgt_se=target_se,
            output_path=str(output_path),
        )
        return {
            "status": "success",
            "audio_url": f"/audio/{output_id}_output.wav",
            "original_audio_url": f"/audio/{output_id}_base.wav",
        }
    else:
        return {
            "status": "success",
            "audio_url": f"/audio/{output_id}_base.wav",
            "original_audio_url": f"/audio/{output_id}_base.wav",
        }


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve generated audio files."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(file_path, media_type="audio/wav")
