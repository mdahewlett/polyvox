.PHONY: backend frontend be fe

backend be:
	cd backend && uv run uvicorn main:app --reload

frontend fe:
	cd frontend && npm run dev
