#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FormatNormalizer Cloud Function
==============================

This module provides a Google Cloud Function entrypoint for the FormatNormalizer.
It handles incoming HTTP requests and forwards them to the normalizer.
"""

import os
import json
import logging
import asyncio
import tempfile
import functions_framework
from flask import Request, jsonify
from werkzeug.utils import secure_filename
import google.cloud.storage as storage

# Import the normalizer
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.normalizer import FormatNormalizer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize the normalizer
normalizer = FormatNormalizer()

# Initialize GCS client
storage_client = storage.Client()

# Get configuration from environment
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'format-normalizer-output')
TEMP_DIR = os.environ.get('TEMP_DIR', '/tmp')

@functions_framework.http
def normalize_http(request: Request):
    """
    HTTP Cloud Function entry point.
    
    Args:
        request: The HTTP request
        
    Returns:
        HTTP response
    """
    try:
        # Determine the request type
        if request.method == 'GET':
            return jsonify({
                "status": "ok",
                "service": "FormatNormalizer",
                "version": "1.0.0"
            })
        
        elif request.method == 'POST':
            # Check if this is a file upload or a JSON request
            content_type = request.headers.get('Content-Type', '')
            
            if 'multipart/form-data' in content_type:
                return handle_file_upload(request)
            else:
                return handle_json_request(request)
        
        else:
            return jsonify({
                "error": "Method not allowed"
            }), 405
    
    except Exception as e:
        logger.error(f"Error handling request: {e}")
        return jsonify({
            "error": str(e)
        }), 500

def handle_file_upload(request: Request):
    """
    Handle file upload request.
    
    Args:
        request: The HTTP request with uploaded file
        
    Returns:
        HTTP response
    """
    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    
    # If the user does not select a file, browser submits an empty part
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    try:
        # Create temporary directory for the uploaded file
        temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        
        # Save the uploaded file
        file_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(file_path)
        
        # Extract parameters from form data
        target_format = request.form.get('format')
        codec = request.form.get('codec')
        preset = request.form.get('preset')
        preserve_metadata = request.form.get('preserve_metadata', 'true').lower() == 'true'
        enable_ai = request.form.get('enable_ai', 'false').lower() == 'true'
        validate_output = request.form.get('validate_output', 'true').lower() == 'true'
        
        # Process the normalization
        result = asyncio.run(
            normalizer.normalize(
                source=file_path,
                target_format=target_format,
                codec=codec,
                preset=preset,
                options={
                    "preserveMetadata": preserve_metadata,
                    "enableAI": enable_ai,
                    "validateOutput": validate_output
                }
            )
        )
        
        # If normalization was successful, upload the result to GCS
        if result.get("success", False):
            output_path = result.get("result", {}).get("uri")
            if output_path and os.path.exists(output_path):
                # Upload to GCS
                gcs_path = upload_to_gcs(output_path, OUTPUT_BUCKET)
                
                # Update the result with GCS path
                result["result"]["gcs_uri"] = gcs_path
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return jsonify({"error": str(e)}), 500

def handle_json_request(request: Request):
    """
    Handle JSON request.
    
    Args:
        request: The HTTP request with JSON payload
        
    Returns:
        HTTP response
    """
    try:
        # Parse JSON request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Extract parameters
        source_uri = data.get("source", {}).get("uri")
        if not source_uri:
            return jsonify({"error": "Source URI is required"}), 400
        
        target = data.get("target", {})
        options = data.get("options", {})
        
        # Process the normalization
        result = asyncio.run(
            normalizer.normalize(
                source=source_uri,
                target_format=target.get("format"),
                codec=target.get("codec"),
                preset=target.get("preset"),
                options={
                    "preserveMetadata": options.get("preserveMetadata", True),
                    "enableAI": options.get("enableAI", False),
                    "validateOutput": options.get("validateOutput", True)
                }
            )
        )
        
        # If normalization was successful, upload the result to GCS
        if result.get("success", False):
            output_path = result.get("result", {}).get("uri")
            if output_path and os.path.exists(output_path):
                # Upload to GCS
                gcs_path = upload_to_gcs(output_path, OUTPUT_BUCKET)
                
                # Update the result with GCS path
                result["result"]["gcs_uri"] = gcs_path
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

def upload_to_gcs(file_path: str, bucket_name: str) -> str:
    """
    Upload a file to Google Cloud Storage.
    
    Args:
        file_path: Path to the file to upload
        bucket_name: Name of the GCS bucket
        
    Returns:
        GCS URI of the uploaded file
    """
    try:
        # Get the bucket
        bucket = storage_client.bucket(bucket_name)
        
        # Generate a unique object name
        object_name = f"outputs/{os.path.basename(file_path)}"
        
        # Upload the file
        blob = bucket.blob(object_name)
        blob.upload_from_filename(file_path)
        
        # Return the GCS URI
        return f"gs://{bucket_name}/{object_name}"
    
    except Exception as e:
        logger.error(f"Error uploading to GCS: {e}")
        raise

# For local testing
if __name__ == "__main__":
    from flask import Flask, request
    
    app = Flask(__name__)
    
    @app.route('/', methods=['GET', 'POST'])
    def local_function():
        return normalize_http(request)
    
    app.run(host='0.0.0.0', port=8080, debug=True)