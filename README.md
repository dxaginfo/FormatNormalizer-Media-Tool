# FormatNormalizer Media Tool

FormatNormalizer is an advanced media format normalization tool designed to streamline and standardize various media formats for consistent processing and delivery. Using FFmpeg as its core processing engine with Python orchestration and Google Cloud integration, FormatNormalizer provides intelligent format conversion, optimization, and validation to ensure media compatibility across different platforms and workflows.

## Features

- **Format Conversion**: Convert between a wide range of media formats (video, audio, image sequences)
- **Intelligent Optimization**: Gemini AI integration for content-aware encoding decisions
- **Batch Processing**: Process multiple files with consistent settings
- **Media Validation**: Ensures output meets technical specifications
- **Cloud Deployment**: Deploy on Google Cloud Functions or Cloud Run
- **API-First Design**: RESTful API for easy integration with other tools

## Technical Architecture

The system consists of the following core components:

1. **Normalization Engine** - Python with FFmpeg integration
   - Handles format conversion logic
   - Manages encoding/decoding processes
   - Implements quality control mechanisms

2. **AI Analysis Module** - Gemini API integration
   - Analyzes content characteristics
   - Recommends optimal encoding parameters
   - Identifies potential conversion issues

3. **Processing Pipeline** - Google Cloud Functions and Run
   - Orchestrates conversion workflows
   - Manages distributed processing
   - Handles error recovery and retries

4. **Metadata Management** - Custom implementation
   - Preserves essential metadata during conversion
   - Maps metadata between different format specifications
   - Generates technical compliance reports

## Implementation Technologies

- **Core Language**: Python 3.9+
- **Media Processing**: FFmpeg, FFprobe
- **Cloud Infrastructure**: Google Cloud Functions, Cloud Run, Cloud Storage
- **AI Integration**: Gemini API
- **Quality Control**: VMAF, SSIM, PSNR metrics

## Setup Instructions

### Local Development Setup

1. Clone the repository:
   ```
   git clone https://github.com/dxaginfo/FormatNormalizer-Media-Tool.git
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Install FFmpeg:
   - On Ubuntu: `sudo apt-get install ffmpeg`
   - On macOS: `brew install ffmpeg`
   - On Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

5. Configure Google Cloud credentials (optional for Gemini API and GCS integration):
   ```
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
   ```

6. Start the API server:
   ```
   uvicorn src.api:app --reload
   ```

### Cloud Deployment

#### Google Cloud Functions

1. Set up Google Cloud project and enable necessary APIs:
   - Cloud Functions API
   - Cloud Build API
   - Cloud Storage API

2. Deploy the Cloud Function:
   ```
   gcloud functions deploy format-normalizer \
     --runtime python39 \
     --trigger-http \
     --entry-point normalize_http \
     --source deploy/ \
     --memory 2048MB \
     --timeout 540s \
     --env-vars-file .env.yaml
   ```

#### Google Cloud Run

1. Build the Docker image:
   ```
   docker build -t gcr.io/[PROJECT_ID]/format-normalizer -f deploy/Dockerfile .
   ```

2. Push to Google Container Registry:
   ```
   docker push gcr.io/[PROJECT_ID]/format-normalizer
   ```

3. Deploy to Cloud Run:
   ```
   gcloud run deploy format-normalizer \
     --image gcr.io/[PROJECT_ID]/format-normalizer \
     --platform managed \
     --memory 2G \
     --cpu 2 \
     --timeout 15m \
     --env-vars-file .env.yaml
   ```

## API Usage

### Basic Format Conversion

```python
from format_normalizer import FormatNormalizer

async def convert_video_to_mp4(video_path):
    normalizer = FormatNormalizer()
    
    result = await normalizer.normalize(
        source=video_path,
        target_format="mp4",
        codec="h264",
        preset="web"
    )
    
    print(f"Converted video available at: {result['result']['uri']}")
    return result
```

### Batch Processing

```python
from format_normalizer import FormatNormalizer, BatchProcessor

async def batch_convert_to_av1(media_directory, output_directory):
    normalizer = FormatNormalizer()
    batch = BatchProcessor(normalizer)
    
    # Add all media files from directory
    batch.add_directory(
        media_directory,
        target={
            "format": "mp4",
            "codec": "av1",
            "preset": "quality"
        },
        options={
            "enableAI": True,
            "validateOutput": True
        },
        output_directory=output_directory
    )
    
    # Process the batch
    results = await batch.process()
    return results
```

### RESTful API

The tool includes a RESTful API for remote operation:

```bash
# Submit a normalization job
curl -X POST "http://localhost:8000/api/normalize" \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "uri": "https://example.com/video.mov"
    },
    "target": {
      "format": "mp4",
      "codec": "h264",
      "preset": "web"
    },
    "options": {
      "preserveMetadata": true,
      "enableAI": true,
      "validateOutput": true
    }
  }'
```

## Integration with Other Tools

FormatNormalizer is designed to integrate with other media tools:

- SceneValidator: For validating scene content before normalization
- VeoPromptExporter: For exporting prompts with normalized media
- TimelineAssembler: For assembling normalized media into timelines
- LoopOptimizer: For optimizing loop sequences with standardized formats

## License

MIT License

## Contact and Support

- GitHub Issues: [Issues](https://github.com/dxaginfo/FormatNormalizer-Media-Tool/issues)
- Documentation: [Specification Document](https://docs.google.com/document/d/13xo4eZSrx-fz0Ui3nRowSIqbSp3Yt2La2HHrDKbZOkc)