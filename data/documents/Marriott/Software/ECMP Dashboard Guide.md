

cd hotelops-osdchat-ecmp-ai-dashboard
source ~/.zshrc   # if you rely on cert env for anything else
.venv/bin/python -m uvicorn src.adapters.inbound.server:app --reload --host 0.0.0.0 --port 8080