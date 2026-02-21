.PHONY: backend frontend be fe sync install

sync:
	cd backend && uv sync
	cd backend && uv pip install -e ./OpenVoice --no-deps

install:
	cd frontend && npm i

backend be:
	cd backend && PYTHONUNBUFFERED=1 uv run uvicorn main:app --reload

frontend fe:
	cd frontend && npm run dev
