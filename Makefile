.PHONY: backend frontend be fe sync install

sync:
	cd backend && uv sync --inexact
	cd backend && uv pip install -e ./OpenVoice --no-deps

# Optional: for OpenVoice base speaker voices (requires base_speakers checkpoints)
# tokenizers<0.14 required by MeloTTS's transformers; setuptools<82 for pkg_resources (pykakasi)
sync-melotts:
	cd backend && uv pip install "tokenizers>=0.11.1,!=0.11.3,<0.14" "setuptools<82"
	cd backend && uv pip install "git+https://github.com/myshell-ai/MeloTTS.git"
	cd backend && uv pip install "tokenizers>=0.11.1,!=0.11.3,<0.14"
	cd backend && .venv/bin/python -m unidic download

install:
	cd frontend && npm i

backend be:
	cd backend && PYTHONUNBUFFERED=1 uv run --no-sync uvicorn main:app --reload

frontend fe:
	cd frontend && npm run dev
