.PHONY: build up down restart logs status dbshell reindex backup smoke migrate install-launchd uninstall-launchd \
	quality-install quality-soft quality-bootstrap

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f api

status:
	docker compose ps

dbshell:
	docker compose exec postgres psql -U secondbrain secondbrain

reindex:
	curl -s -X POST http://localhost:8000/reindex | python3 -m json.tool

backup:
	bash scripts/backup.sh

smoke:
	bash scripts/smoke.sh

migrate:
	docker compose exec api alembic upgrade head

install-launchd:
	cp launchd/com.vamshi.secondbrain.plist ~/Library/LaunchAgents/
	cp launchd/com.vamshi.secondbrain.backup.plist ~/Library/LaunchAgents/
	launchctl load ~/Library/LaunchAgents/com.vamshi.secondbrain.plist
	launchctl load ~/Library/LaunchAgents/com.vamshi.secondbrain.backup.plist
	@echo "Installed. Stack starts on login. Backup runs daily at 3am."

uninstall-launchd:
	launchctl unload ~/Library/LaunchAgents/com.vamshi.secondbrain.plist 2>/dev/null || true
	launchctl unload ~/Library/LaunchAgents/com.vamshi.secondbrain.backup.plist 2>/dev/null || true
	rm -f ~/Library/LaunchAgents/com.vamshi.secondbrain.plist
	rm -f ~/Library/LaunchAgents/com.vamshi.secondbrain.backup.plist
	@echo "Uninstalled."

# --- AI quality toolkit (soft launch) ---
quality-bootstrap:
	bash ../engineering-standards/scripts/bootstrap.sh --stack=python,typescript --target=. --coverage=80
	@echo "Bootstrap done. Run: make quality-install"

quality-install:
	pip install -r requirements/quality.txt
	cd frontend && npm install
	pre-commit install --hook-type pre-commit --hook-type commit-msg
	@echo "Installed. Restart Cursor. Run: make quality-soft"

quality-soft:
	bash scripts/quality-soft.sh
