import os
import json
import tempfile
import functions_framework
from flask import Request, jsonify
from google.cloud import storage, firestore
import uuid
from datetime import datetime
import sys
import logging

# Add the project root to the Python path
sys.path.append('/tmp')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize cloud clients
storage_client = storage.Client()
bucket_name = os.environ.get('GCS_BUCKET_NAME', 'format-normalizer-media')
bucket = storage_client.bucket(bucket_name)

db = firestore.Client()
collection_name = os.environ.get('FIRESTORE_COLLECTION', 'normalization_jobs')

def download_from_gcs(source_uri, local_path):
    """Download a file from Google Cloud Storage to a local path."""
    if not source_uri.startswith('gs://'):
        # Not a GCS URI, might be an HTTP URL
        return False
    
    # Parse the GCS URI
    # Format: gs://bucket-name/path/to/file
    parts = source_uri[5:].split('/', 1)
    source_bucket_name = parts[0]
    blob_name = parts[1] if len(parts) > 1 else ''
    
    # Download the file
    source_bucket = storage_client.bucket(source_bucket_name)
    blob = source_bucket.blob(blob_name)
    blob.download_to_filename(local_path)
    
    return True

def upload_to_gcs(local_path, destination_blob_name):
    """Upload a file to Google Cloud Storage."""
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_path)
    return blob.public_url

def import_format_normalizer():
    """Dynamically import the FormatNormalizer module."""
    try:
        # First, try to import directly (if deployed with the function)
        from format_normalizer import FormatNormalizer
        return FormatNormalizer
    except ImportError:
        # If not available, download from GCS and install
        logger.info("FormatNormalizer not found, downloading from GCS...")
        
        # Create a temp directory for the package
        package_dir = '/tmp/format_normalizer_package'
        os.makedirs(package_dir, exist_ok=True)
        
        # Download the package
        package_blob = bucket.blob('packages/format_normalizer.zip')
        package_path = f"{package_dir}/format_normalizer.zip"
        package_blob.download_to_filename(package_path)
        
        # Extract and install the package
        import zipfile
        with zipfile.ZipFile(package_path, 'r') as zip_ref:
            zip_ref.extractall(package_dir)
        
        # Add to path and import
        sys.path.append(package_dir)
        from format_normalizer import FormatNormalizer
        return FormatNormalizer

@functions_framework.http
def normalize_media(request: Request):
    """Cloud Function to normalize media files."""
    # Create a unique job ID
    job_id = str(uuid.uuid4())
    
    # Create job document in Firestore
    job_ref = db.collection(collection_name).document(job_id)
    job_ref.set({
        'id': job_id,
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    })
    
    try:
        # Parse request
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                # JSON request (source URL + params)
                data = request.get_json()
                source_uri = data.get('source', {}).get('uri')
                target_format = data.get('target', {})
                options = data.get('options', {})
                
                if not source_uri:
                    return jsonify({'error': 'Source URI is required'}), 400
                
                # Update job with request data
                job_ref.update({
                    'source': source_uri,
                    'target_format': target_format,
                    'options': options
                })
                
                # Process the normalization asynchronously
                process_normalization.call_async(job_id, source_uri, target_format, options)
                
                return jsonify({
                    'job_id': job_id,
                    'status': 'pending',
                    'message': 'Normalization job submitted successfully'
                })
            
            elif request.content_type.startswith('multipart/form-data'):
                # Multipart request (file upload + params)
                if 'file' not in request.files:
                    return jsonify({'error': 'No file uploaded'}), 400
                
                # Get the uploaded file
                uploaded_file = request.files['file']
                
                # Get form parameters
                target_format_str = request.form.get('target_format', '{}')
                preset = request.form.get('preset', 'standard')
                enable_ai = request.form.get('enable_ai', '').lower() == 'true'
                validate_output = request.form.get('validate_output', '').lower() == 'true'
                priority = request.form.get('priority', 'normal')
                
                try:
                    target_format = json.loads(target_format_str)
                except json.JSONDecodeError:
                    return jsonify({'error': 'Invalid target_format JSON'}), 400
                
                # Save the file to a temporary location
                temp_dir = tempfile.mkdtemp()
                source_path = os.path.join(temp_dir, uploaded_file.filename)
                uploaded_file.save(source_path)
                
                # Upload to GCS
                source_blob_name = f"uploads/{job_id}/{uploaded_file.filename}"
                upload_to_gcs(source_path, source_blob_name)
                source_uri = f"gs://{bucket_name}/{source_blob_name}"
                
                # Build options
                options = {
                    'preset': preset,
                    'enableAI': enable_ai,
                    'validateOutput': validate_output,
                    'priority': priority
                }
                
                # Update job with request data
                job_ref.update({
                    'source': source_uri,
                    'target_format': target_format,
                    'options': options
                })
                
                # Process the normalization asynchronously
                process_normalization.call_async(job_id, source_uri, target_format, options)
                
                return jsonify({
                    'job_id': job_id,
                    'status': 'pending',
                    'message': 'Normalization job submitted successfully'
                })
            
            else:
                return jsonify({'error': 'Unsupported content type'}), 415
        
        elif request.method == 'GET':
            # Return job details if job_id is provided
            job_id = request.args.get('job_id')
            if job_id:
                job_doc = db.collection(collection_name).document(job_id).get()
                if job_doc.exists:
                    return jsonify(job_doc.to_dict())
                else:
                    return jsonify({'error': 'Job not found'}), 404
            
            # List jobs with optional filters
            status = request.args.get('status')
            limit = int(request.args.get('limit', 100))
            
            query = db.collection(collection_name)
            if status:
                query = query.where('status', '==', status)
            
            query = query.order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
            jobs = [doc.to_dict() for doc in query.stream()]
            
            return jsonify(jobs)
        
        else:
            return jsonify({'error': 'Method not allowed'}), 405
    
    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        
        # Update job with error
        job_ref.update({
            'status': 'failed',
            'error': str(e),
            'completed_at': datetime.now().isoformat()
        })
        
        return jsonify({'error': str(e)}), 500

@functions_framework.cloud_event
def process_normalization(cloud_event):
    """Background Cloud Function to process a normalization job."""
    data = cloud_event.data
    job_id = data.get('job_id')
    source_uri = data.get('source_uri')
    target_format = data.get('target_format')
    options = data.get('options', {})
    
    # Get job reference
    job_ref = db.collection(collection_name).document(job_id)
    
    try:
        # Update job status to processing
        job_ref.update({
            'status': 'processing',
            'updated_at': datetime.now().isoformat()
        })
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Download source file
        source_filename = os.path.basename(source_uri.split('/')[-1])
        source_local_path = os.path.join(temp_dir, source_filename)
        
        if source_uri.startswith('gs://'):
            download_from_gcs(source_uri, source_local_path)
        else:
            # Handle HTTP URLs or other sources
            import requests
            response = requests.get(source_uri, stream=True)
            with open(source_local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # Prepare output path
        output_format = target_format.get('format', 'mp4')
        output_filename = f"normalized_{source_filename.split('.')[0]}.{output_format}"
        output_local_path = os.path.join(temp_dir, output_filename)
        
        # Dynamically import FormatNormalizer
        FormatNormalizer = import_format_normalizer()
        
        # Initialize normalizer
        normalizer = FormatNormalizer(
            ai_api_key=os.environ.get('GEMINI_API_KEY'),
            temp_dir=temp_dir
        )
        
        # Run normalization
        result = await normalizer.normalize(
            source_path=source_local_path,
            output_path=output_local_path,
            target_format=target_format,
            preset=options.get('preset', 'standard'),
            enable_ai=options.get('enableAI', False),
            validate_output=options.get('validateOutput', True)
        )
        
        # Upload result to GCS
        output_blob_name = f"results/{job_id}/{output_filename}"
        result_url = upload_to_gcs(output_local_path, output_blob_name)
        
        # Update job with results
        job_ref.update({
            'status': 'completed',
            'result': result,
            'result_url': result_url,
            'completed_at': datetime.now().isoformat()
        })
        
        # Clean up temporary files
        import shutil
        shutil.rmtree(temp_dir)
        
        return {'status': 'completed', 'job_id': job_id, 'result_url': result_url}
    
    except Exception as e:
        logger.exception(f"Error processing normalization job {job_id}: {e}")
        
        # Update job with error
        job_ref.update({
            'status': 'failed',
            'error': str(e),
            'completed_at': datetime.now().isoformat()
        })
        
        return {'status': 'failed', 'job_id': job_id, 'error': str(e)}