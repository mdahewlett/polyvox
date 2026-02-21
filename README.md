# Polyvox - Accent Trainer

Record your voice, hear how it would sound in different accents, and mimick yourself.

## Prerequisites

- Python 3.10+, Node.js, ffmpeg, [uv](https://docs.astral.sh/uv/)
- **OpenVoice**: Clone [myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice) into `backend/`, place converter checkpoints in `backend/checkpoints_v2/converter/`
- **AWS credentials** for Amazon Polly TTS

## Quick start

```bash
make sync && make install
make backend   # terminal 1
make frontend  # terminal 2
```

Open <http://localhost:3000>

## OpenVoice Base Speakers (optional)

To use OpenVoice base speaker voices (e.g. en-default, en-us) in addition to Polly:

1. Ensure `checkpoints_v2/base_speakers/ses/` contains `.pth` files (from the full OpenVoice V2 checkpoint).
2. Run `make sync-melotts`.
