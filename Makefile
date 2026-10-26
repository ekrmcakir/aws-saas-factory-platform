.PHONY: help install test demo clean terraform-fmt terraform-validate

help:
	@echo "AWS Enterprise SaaS Factory Platform Blueprint"
	@echo "=============================================="
	@echo "make install      : Set up python virtual environment & dependencies"
	@echo "make test         : Run automated test suite with pytest"
	@echo "make demo         : Run interactive terminal simulation"
	@echo "make terraform-fmt: Format Terraform configurations"
	@echo "make clean        : Remove caches, venv and temporary files"

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

test:
	PYTHONPATH=. .venv/bin/pytest tests/ -v

demo:
	PYTHONPATH=. .venv/bin/python3 scripts/run_demo.py

terraform-fmt:
	terraform -chdir=infra/terraform fmt -recursive

clean:
	rm -rf .venv __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
