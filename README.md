# FormatNormalizer Media Automation Tool

FormatNormalizer is an automated media format conversion and standardization tool for media workflows. It uses FFmpeg for processing and Google Cloud for storage and deployment.

## Features
- Accepts video, audio, and image files
- Uses Gemini API for parameter optimization
- FFmpeg-based core engine
- Automated quality control
- API and web interface

## Setup
- Python 3.9+
- FFmpeg (install on your system)
- Google Cloud credentials (for Cloud Run/Functions)

## Usage
- REST API `/api/normalize` to submit a normalization job
- `/api/jobs/{jobId}` to check status
- `/api/presets` to retrieve available presets

See the [specification doc](https://docs.google.com/document/d/1HPsPTZ1w1_9W6uJ1n2JdGsJCRVUUSIcbsipXR1AJq30) for details.
