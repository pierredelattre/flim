.PHONY: dev backend frontend

dev:
	@echo "🚀 Lancement backend + frontend..."
	(cd backend && .venv/bin/uvicorn main:app --reload &) \
	&& (cd frontend && npm run dev)

backend:
	cd backend && .venv/bin/uvicorn main:app --reload

frontend:
	cd frontend && npm run dev
