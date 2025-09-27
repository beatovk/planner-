PYTHON ?= python3
APP_DIR := entertainment-planner-api
PORT ?= 8000
BASE ?= http://localhost:$(PORT)

.PHONY: setup run test smoke

setup:
	$(PYTHON) -m pip install -r $(APP_DIR)/requirements.txt

run:
	uvicorn apps.api.main:app --app-dir $(APP_DIR) --host 0.0.0.0 --port $(PORT) --workers 1

test:
	PYTHONPATH=$(APP_DIR) $(PYTHON) -m pytest $(APP_DIR)/tests

smoke:
	BASE=$(BASE) $(PYTHON) scripts/smoke_tests.py
