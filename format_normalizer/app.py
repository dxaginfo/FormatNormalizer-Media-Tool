from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
import os
import uuid
import json
import asyncio
from datetime import datetime
import logging

from .normalizer import FormatNormalizer
from .ai_analyzer import AIAnalysisModule
from .cloud_integration import CloudStorageManager, FirestoreManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="FormatNormalizer API",
    description="API for media format normalization and conversion",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global variables for services
normalizer = None
ai_module = None
storage_manager = None
firestore_manager = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    global normalizer, ai_module, storage_manager, firestore_manager
    
    # Get configuration from environment variables
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    gcs_bucket_name = os.environ.get("GCS_BUCKET_NAME", "format-normalizer-media")
    firestore_collection = os.environ.get("FIRESTORE_COLLECTION", "normalization_jobs")
    
    # Initialize services
    normalizer = FormatNormalizer()
    ai_module = AIAnalysisModule(api_key=gemini_api_key)
    
    # Initialize cloud services if running in cloud environment
    if os.environ.get("CLOUD_RUN") or os.environ.get("CLOUD_FUNCTIONS"):
        storage_manager = CloudStorageManager(bucket_name=gcs_bucket_name)
        firestore_manager = FirestoreManager(collection_name=firestore_collection)

@app.get("/")
async def root():
    """Root endpoint providing basic API information."""
    return {
        "name": "FormatNormalizer API",
        "version": "1.0.0",
        "documentation": "/docs",
        "status": "running"
    }

@app.post("/api/normalize")
async def normalize_media(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    source_url: Optional[str] = Form(None),
    target_format: str = Form(...),
    preset: Optional[str] = Form("standard"),
    enable_ai: bool = Form(False),
    validate_output: bool = Form(True),
    priority: str = Form("normal")
):
    """Submit a media file for normalization.
    
    Either upload a file or provide a source URL pointing to the media file.
    Specify the target format and additional options for the conversion.
    
    Returns a job ID that can be used to check the status of the normalization process.
    """
    if not file and not source_url:
        raise HTTPException(status_code=400, detail="Either file upload or source URL must be provided")
    
    # Parse target format JSON
    try:
        target_format_dict = json.loads(target_format)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid target_format JSON")
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Create a temporary directory for this job
    job_dir = f"/tmp/{job_id}"
    os.makedirs(job_dir, exist_ok=True)
    
    # Prepare job data
    job_data = {
        "id": job_id,
        "created_at": datetime.now().isoformat(),
        "status": "pending",
        "source": source_url if source_url else "uploaded_file",
        "target_format": target_format_dict,
        "preset": preset,
        "enable_ai": enable_ai,
        "validate_output": validate_output,
        "priority": priority
    }
    
    # Save job data to Firestore if available
    if firestore_manager:
        await firestore_manager.create_job(job_data)
    
    # Add normalization task to background tasks
    background_tasks.add_task(
        process_normalization_job,
        job_id=job_id,
        job_dir=job_dir,
        file=file,
        source_url=source_url,
        target_format_dict=target_format_dict,
        preset=preset,
        enable_ai=enable_ai,
        validate_output=validate_output
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Normalization job submitted successfully"
    }

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a normalization job."""
    if firestore_manager:
        job_data = await firestore_manager.get_job(job_id)
        if job_data:
            return job_data
    
    # If not using Firestore or job not found
    raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")

@app.get("/api/jobs")
async def list_jobs(status: Optional[str] = None, limit: int = 100):
    """List normalization jobs with optional status filter."""
    if firestore_manager:
        filters = {"status": status} if status else None
        jobs = await firestore_manager.list_jobs(filters=filters, limit=limit)
        return jobs
    
    # If not using Firestore
    raise HTTPException(status_code=501, detail="Job listing not available without Firestore integration")

@app.get("/api/presets")
async def get_presets():
    """Get available normalization presets."""
    return {
        "presets": [
            {
                "name": "web",
                "description": "Optimized for web delivery, good balance of quality and file size",
                "formats": ["mp4", "webm", "mp3", "jpg", "png"]
            },
            {
                "name": "social",
                "description": "Optimized for social media platforms",
                "formats": ["mp4", "mov", "mp3", "jpg"]
            },
            {
                "name": "broadcast",
                "description": "High quality for broadcast delivery",
                "formats": ["mov", "mxf", "wav"]
            },
            {
                "name": "archive",
                "description": "Maximum quality for archival purposes",
                "formats": ["mov", "mxf", "wav", "tiff"]
            },
            {
                "name": "mobile",
                "description": "Optimized for mobile devices with lower bandwidth",
                "formats": ["mp4", "mp3", "jpg"]
            }
        ]
    }

@app.get("/api/formats")
async def get_formats():
    """Get supported media formats and codecs."""
    return {
        "video": {
            "formats": ["mp4", "mov", "mkv", "webm", "mxf", "avi"],
            "codecs": ["h264", "h265", "prores", "av1", "vp9", "dnxhd", "xvid"]
        },
        "audio": {
            "formats": ["mp3", "wav", "aac", "flac", "ogg", "m4a"],
            "codecs": ["mp3", "aac", "flac", "opus", "pcm", "vorbis"]
        },
        "image": {
            "formats": ["jpg", "png", "tiff", "webp", "avif"],
            "codecs": ["jpeg", "png", "tiff", "webp", "avif"]
        }
    }

async def process_normalization_job(job_id: str, job_dir: str, file: Optional[UploadFile], 
                                  source_url: Optional[str], target_format_dict: Dict[str, Any],
                                  preset: str, enable_ai: bool, validate_output: bool):
    """Background task to process a normalization job."""
    try:
        # Update job status to processing
        if firestore_manager:
            await firestore_manager.update_job(job_id, {"status": "processing"})
        
        # Save the uploaded file or download from URL
        source_path = None
        if file:
            source_path = f"{job_dir}/source_{file.filename}"
            with open(source_path, "wb") as f:
                content = await file.read()
                f.write(content)
        elif source_url:
            source_path = f"{job_dir}/source_file"
            # Download from URL logic
            # For cloud deployment, use storage_manager
            if storage_manager and source_url.startswith("gs://"):
                blob_name = source_url.replace("gs://", "").split("/", 1)[1]
                source_path = await storage_manager.download_file(blob_name, source_path)
            else:
                # Use requests or aiohttp to download from HTTP URL
                pass
        
        # Destination path for normalized file
        output_path = f"{job_dir}/normalized_output.{target_format_dict.get('format', 'mp4')}"
        
        # Perform normalization
        normalization_result = await normalizer.normalize(
            source_path=source_path,
            output_path=output_path,
            target_format=target_format_dict,
            preset=preset,
            enable_ai=enable_ai,
            validate_output=validate_output
        )
        
        # Upload the result to Cloud Storage if available
        result_url = None
        if storage_manager and os.path.exists(output_path):
            blob_name = f"normalized/{job_id}/{os.path.basename(output_path)}"
            result_url = await storage_manager.upload_file(output_path, blob_name)
        
        # Update job with results
        job_result = {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "result": normalization_result,
            "result_url": result_url
        }
        
        if firestore_manager:
            await firestore_manager.update_job(job_id, job_result)
        
        # Clean up temporary files
        if os.path.exists(job_dir):
            import shutil
            shutil.rmtree(job_dir)
            
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        
        # Update job with error
        error_data = {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        }
        
        if firestore_manager:
            await firestore_manager.update_job(job_id, error_data)
        
        # Clean up temporary files
        if os.path.exists(job_dir):
            import shutil
            shutil.rmtree(job_dir)