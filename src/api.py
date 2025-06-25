#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FormatNormalizer API Module
===========================

This module provides a RESTful API for the FormatNormalizer tool,
allowing for HTTP-based interaction with the normalization functionality.
"""

import os
import json
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import tempfile
import shutil

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .normalizer import FormatNormalizer, BatchProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="FormatNormalizer API",
    description="API for media format conversion and standardization",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the normalizer
normalizer = FormatNormalizer()

# In-memory job storage (in production, use a proper database)
jobs = {}

# Input models
class NormalizationOptions(BaseModel):
    preserveMetadata: bool = True
    enableAI: bool = False
    validateOutput: bool = True
    priority: str = "normal"

class NormalizationTarget(BaseModel):
    format: Optional[str] = None
    codec: Optional[str] = None
    preset: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class NormalizationRequest(BaseModel):
    source: Dict[str, Any]
    target: NormalizationTarget
    options: Optional[NormalizationOptions] = None

class JobQuery(BaseModel):
    job_id: str

# Routes
@app.get("/")
async def root():
    """API root endpoint."""
    return {"message": "FormatNormalizer API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/presets")
async def get_presets():
    """Retrieve available presets."""
    return {"presets": list(normalizer.presets.keys())}

@app.post("/api/normalize")
async def normalize_media(request: NormalizationRequest):
    """
    Normalize a media file according to the provided specifications.
    
    The source file must be accessible at the provided URI.
    """
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Store job information
        jobs[job_id] = {
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "request": request.dict()
        }
        
        # Process the normalization request asynchronously
        asyncio.create_task(
            process_normalization_job(job_id, request)
        )
        
        return {"job_id": job_id, "status": "pending"}
        
    except Exception as e:
        logger.error(f"Error handling normalization request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/normalize/upload")
async def normalize_uploaded_media(
    file: UploadFile = File(...),
    format: Optional[str] = Form(None),
    codec: Optional[str] = Form(None),
    preset: Optional[str] = Form(None),
    preserve_metadata: bool = Form(True),
    enable_ai: bool = Form(False),
    validate_output: bool = Form(True),
):
    """
    Upload and normalize a media file.
    
    This endpoint accepts file uploads and processes them according to the provided parameters.
    """
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create temporary directory for the uploaded file
        upload_dir = os.path.join(tempfile.gettempdir(), f"upload_{job_id}")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save the uploaded file
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Create normalization request
        request = NormalizationRequest(
            source={"uri": file_path},
            target=NormalizationTarget(
                format=format,
                codec=codec,
                preset=preset
            ),
            options=NormalizationOptions(
                preserveMetadata=preserve_metadata,
                enableAI=enable_ai,
                validateOutput=validate_output
            )
        )
        
        # Store job information
        jobs[job_id] = {
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "request": request.dict(),
            "upload_dir": upload_dir
        }
        
        # Process the normalization request asynchronously
        asyncio.create_task(
            process_normalization_job(job_id, request)
        )
        
        return {"job_id": job_id, "status": "pending"}
        
    except Exception as e:
        logger.error(f"Error handling file upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a normalization job.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]

@app.get("/api/jobs/{job_id}/download")
async def download_job_result(job_id: str):
    """
    Download the result of a completed normalization job.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    if "result" not in job or "uri" not in job["result"]:
        raise HTTPException(status_code=500, detail="Job result not available")
    
    file_path = job["result"]["uri"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=os.path.basename(file_path)
    )

@app.get("/api/jobs")
async def list_jobs(
    status: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    List normalization jobs with optional filtering.
    """
    filtered_jobs = []
    
    for job_id, job_data in jobs.items():
        if status is None or job_data.get("status") == status:
            # Add job_id to the job data
            job_info = job_data.copy()
            job_info["job_id"] = job_id
            filtered_jobs.append(job_info)
    
    # Sort by creation time (newest first)
    filtered_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Apply pagination
    paginated_jobs = filtered_jobs[offset:offset + limit]
    
    return {
        "jobs": paginated_jobs,
        "total": len(filtered_jobs),
        "limit": limit,
        "offset": offset
    }

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a normalization job and its associated files.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        job = jobs[job_id]
        
        # Clean up temporary directories if they exist
        if "upload_dir" in job and os.path.exists(job["upload_dir"]):
            shutil.rmtree(job["upload_dir"])
        
        # Remove job from the in-memory store
        del jobs[job_id]
        
        return {"status": "deleted", "job_id": job_id}
        
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background processing function
async def process_normalization_job(job_id: str, request: NormalizationRequest):
    """
    Process a normalization job in the background.
    
    Args:
        job_id: The ID of the job
        request: The normalization request
    """
    try:
        # Update job status
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        
        # Extract parameters from the request
        source_uri = request.source.get("uri")
        if not source_uri:
            raise ValueError("Source URI is required")
        
        # Perform normalization
        result = await normalizer.normalize(
            source=source_uri,
            target_format=request.target.format,
            codec=request.target.codec,
            preset=request.target.preset,
            options={
                "preserveMetadata": request.options.preserveMetadata if request.options else True,
                "enableAI": request.options.enableAI if request.options else False,
                "validateOutput": request.options.validateOutput if request.options else True
            } if request.options else None
        )
        
        # Update job with result
        if result.get("success", False):
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = result.get("result", {})
            jobs[job_id]["metadata"] = result.get("metadata", {})
            jobs[job_id]["performance"] = result.get("performance", {})
            jobs[job_id]["validation"] = result.get("validation", {})
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = result.get("error", "Unknown error")
        
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
    
    finally:
        jobs[job_id]["updated_at"] = datetime.now().isoformat()

# Command-line interface
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)