# Prérequis : uv (https://docs.astral.sh/uv/)
UV ?= uv

setup:
	$(UV) sync --locked --all-extras

test:             ## tests fermés, sans réseau
	$(UV) run pytest

lint:
	$(UV) run ruff check .

all:              ## fetch + lab + futur + figures (réseau requis pour fetch)
	$(UV) run pmf fetch
	$(UV) run pmf lab
	$(UV) run pmf futur
	$(UV) run pmf figures
