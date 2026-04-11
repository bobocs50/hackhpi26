PYTHON ?= /usr/local/bin/python3
APP ?= main:app
HOST ?= 0.0.0.0
PORT ?= 8000
PYTHONPATH ?= src

.PHONY: install dev run

install:
	$(PYTHON) -m pip install -r requirements.txt

dev:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

run:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m uvicorn $(APP) --host $(HOST) --port $(PORT)
