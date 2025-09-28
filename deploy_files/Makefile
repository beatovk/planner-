# Entertainment Planner - Deployment Makefile

# Default base URL for API calls
BASE ?= http://127.0.0.1:8010

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help health version db-diag master-local master-prod deploy-staging deploy-prod dev dev-kill dev-ps api-diag

PORT ?= 8010
HOST ?= 0.0.0.0

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

health: ## Check API health endpoint
	@echo "$(YELLOW)Checking API health...$(NC)"
	@curl -sS "$(BASE)/api/health" | python -m json.tool || echo "$(RED)Health check failed$(NC)"

version: ## Check API version and module fingerprints
	@echo "$(YELLOW)Checking API version...$(NC)"
	@curl -sS "$(BASE)/api/debug/version" | python -m json.tool || echo "$(RED)Version check failed$(NC)"

db-diag: ## Check database diagnostics
	@echo "$(YELLOW)Checking database diagnostics...$(NC)"
	@curl -sS "$(BASE)/api/health/db_diag" | python -m json.tool || echo "$(RED)DB diagnostics failed$(NC)"

master-local: ## Run master tests against local API
	@echo "$(YELLOW)Running master tests against local API...$(NC)"
	@$(MAKE) health
	@$(MAKE) version
	@$(MAKE) db-diag
	@echo "$(YELLOW)Testing search endpoints...$(NC)"
	@curl -sS "$(BASE)/api/places/search?q=test&limit=5" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Search results: {len(data.get(\"results\", []))}')" || echo "$(RED)Search test failed$(NC)"
	@echo "$(YELLOW)Testing rails endpoint...$(NC)"
	@curl -sS "$(BASE)/api/rails?q=i%20wanna%20chill%20movie%20and%20something%20romantic&nocache=1" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Rails results: {len(data.get(\"rails\", []))}')" || echo "$(RED)Rails test failed$(NC)"
	@echo "$(GREEN)Master local tests completed$(NC)"

master-prod: ## Run master tests against production API
	@echo "$(YELLOW)Running master tests against production API...$(NC)"
	@$(MAKE) health
	@$(MAKE) version
	@$(MAKE) db-diag
	@echo "$(YELLOW)Testing search endpoints...$(NC)"
	@curl -sS "$(BASE)/api/places/search?q=test&limit=5" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Search results: {len(data.get(\"results\", []))}')" || echo "$(RED)Search test failed$(NC)"
	@echo "$(YELLOW)Testing rails endpoint...$(NC)"
	@curl -sS "$(BASE)/api/rails?q=i%20wanna%20chill%20movie%20and%20something%20romantic&nocache=1" | python -c "import sys, json; data=json.load(sys.stdin); print(f'Rails results: {len(data.get(\"rails\", []))}')" || echo "$(RED)Rails test failed$(NC)"
	@echo "$(GREEN)Master production tests completed$(NC)"

deploy-staging: ## Deploy to staging (requires fly CLI and app name)
	@echo "$(YELLOW)Deploying to staging...$(NC)"
	@if [ -z "$(APP_NAME)" ]; then echo "$(RED)Please set APP_NAME environment variable$(NC)"; exit 1; fi
	@echo "$(YELLOW)Building and deploying with git ref: $(shell git rev-parse --short HEAD)$(NC)"
	@fly deploy --app $(APP_NAME) --no-cache --build-arg BUILD_REF=$(shell git rev-parse --short HEAD)
	@echo "$(GREEN)Staging deployment completed$(NC)"

deploy-prod: ## Deploy to production (requires fly CLI and app name)
	@echo "$(YELLOW)Deploying to production...$(NC)"
	@if [ -z "$(APP_NAME)" ]; then echo "$(RED)Please set APP_NAME environment variable$(NC)"; exit 1; fi
	@echo "$(YELLOW)Building and deploying with git ref: $(shell git rev-parse --short HEAD)$(NC)"
	@fly deploy --app $(APP_NAME) --no-cache --build-arg BUILD_REF=$(shell git rev-parse --short HEAD)
	@echo "$(GREEN)Production deployment completed$(NC)"

setup-staging: ## Setup staging app and secrets (requires fly CLI)
	@echo "$(YELLOW)Setting up staging app...$(NC)"
	@if [ -z "$(APP_NAME)" ]; then echo "$(RED)Please set APP_NAME environment variable$(NC)"; exit 1; fi
	@fly apps create $(APP_NAME)
	@echo "$(YELLOW)Setting up secrets...$(NC)"
	@echo "$(RED)Please set the following secrets manually:$(NC)"
	@echo "fly secrets set --app $(APP_NAME) \\"
	@echo "  APP_ENV=staging PORT=8000 API_BASE=/api \\"
	@echo "  DATABASE_URL=\"postgresql+psycopg://<ro_user>:<pass>@<host>:6432/<db>\" \\"
	@echo "  ALLOW_TEXT_FALLBACK=0 COMPOSE_DISABLE_PARSER=0 TRACE_RAILS=1"
	@echo "$(GREEN)Staging setup instructions completed$(NC)"

dev-kill:
	-ps aux | awk '/uvicorn .*apps\.api\.main:app/ && !/awk/ {print $$2}' | xargs -I{} kill -9 {} 2>/dev/null || true

dev: dev-kill
	cd "entertainment-planner-api" && \
	PYTHONPATH=. uvicorn apps.api.main:app --host $(HOST) --port $(PORT) --reload

dev-ps:
	ps aux | grep -i "uvicorn .*apps\.api\.main:app" | grep -v grep || true

api-diag:
	curl -sS "$(BASE)/api/health" | python3 -m json.tool || true
	curl -sS "$(BASE)/openapi.json" | python3 - <<'PY' || true
	import sys,json; d=json.load(sys.stdin); print(*sorted(d.get("paths",{}).keys()), sep="\n")
	PY
	curl -sS "$(BASE)/api/health/db_diag" | python3 -m json.tool || true
