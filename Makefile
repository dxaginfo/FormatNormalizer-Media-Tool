# FormatNormalizer Makefile

.PHONY: setup install dev test lint format clean deploy-cloud-run deploy-functions deploy-all

# Environment variables
PYTHON = python3
PIP = $(PYTHON) -m pip
VENV = venv
VENV_BIN = $(VENV)/bin
APP_PORT = 8000
GCS_BUCKET_NAME = format-normalizer-media

# Setup virtual environment
setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt

# Install package
install:
	$(PIP) install -e .

# Run development server
dev:
	$(VENV_BIN)/uvicorn format_normalizer.app:app --reload --port $(APP_PORT)

# Run tests
test:
	$(VENV_BIN)/pytest tests/

# Lint code
lint:
	$(VENV_BIN)/flake8 format_normalizer/
	$(VENV_BIN)/mypy format_normalizer/

# Format code
format:
	$(VENV_BIN)/black format_normalizer/
	$(VENV_BIN)/isort format_normalizer/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Deploy to Cloud Run
deploy-cloud-run:
	gcloud builds submit --config cloudbuild.yaml \
		--substitutions=_GCS_BUCKET_NAME=$(GCS_BUCKET_NAME),_FIRESTORE_COLLECTION=normalization_jobs

# Deploy Cloud Functions
deploy-functions:
	cd functions/normalize_media && \
	gcloud functions deploy normalize-media \
		--runtime=python39 \
		--memory=2048MB \
		--timeout=540s \
		--trigger-http \
		--entry-point=normalize_media \
		--set-env-vars=GCS_BUCKET_NAME=$(GCS_BUCKET_NAME),FIRESTORE_COLLECTION=normalization_jobs
	
	cd functions/batch_processor && \
	gcloud functions deploy batch-processor \
		--runtime=python39 \
		--memory=4096MB \
		--timeout=540s \
		--trigger-topic=format-normalizer-batch-jobs \
		--entry-point=batch_processor \
		--set-env-vars=GCS_BUCKET_NAME=$(GCS_BUCKET_NAME),FIRESTORE_COLLECTION=normalization_jobs

# Deploy all resources
deploy-all: deploy-cloud-run deploy-functions