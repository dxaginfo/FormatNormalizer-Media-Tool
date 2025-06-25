import os
import json
import tempfile
import functions_framework
from google.cloud import storage, firestore, pubsub_v1
import uuid
from datetime import datetime
import sys
import logging
import asyncio

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

publisher = pubsub_v1.PublisherClient()
topic_name = f"projects/{storage_client.project}/topics/format-normalizer-job-results"

@functions_framework.cloud_event
def batch_processor(cloud_event):
    """Background Cloud Function to process a batch of normalization jobs."""
    # Parse the PubSub message
    message_data = cloud_event.data.get('message', {}).get('data', '')
    if not message_data:
        logger.error("No message data received")
        return {'error': 'No message data received'}
    
    try:
        # Decode and parse the message
        import base64
        decoded_message = base64.b64decode(message_data).decode('utf-8')
        batch_job = json.loads(decoded_message)
        
        # Get batch job details
        batch_id = batch_job.get('batch_id') or str(uuid.uuid4())
        source_uris = batch_job.get('source', {}).get('uris', [])
        target_format = batch_job.get('target', {})
        options = batch_job.get('options', {})
        output_config = batch_job.get('output', {})
        
        if not source_uris:
            return {'error': 'No source URIs provided'}
        
        # Create batch job document in Firestore
        batch_ref = db.collection('batch_jobs').document(batch_id)
        batch_ref.set({
            'id': batch_id,
            'status': 'processing',
            'created_at': datetime.now().isoformat(),
            'source_count': len(source_uris),
            'completed_count': 0,
            'failed_count': 0,
            'target_format': target_format,
            'options': options,
            'output': output_config
        })
        
        # Process each source URI
        job_ids = []
        for source_uri in source_uris:
            # Create individual job
            job_id = str(uuid.uuid4())
            job_ref = db.collection(collection_name).document(job_id)
            
            # Add to batch job mapping
            job_ref.set({
                'id': job_id,
                'batch_id': batch_id,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'source': source_uri,
                'target_format': target_format,
                'options': options
            })
            
            # Add to job IDs list
            job_ids.append(job_id)
            
            # Publish message to trigger job processing
            process_job_data = json.dumps({
                'job_id': job_id,
                'source_uri': source_uri,
                'target_format': target_format,
                'options': options
            }).encode('utf-8')
            
            publisher.publish(
                topic_name, 
                data=process_job_data,
                job_id=job_id,
                batch_id=batch_id
            )
        
        # Update batch job with job IDs
        batch_ref.update({
            'job_ids': job_ids
        })
        
        return {
            'batch_id': batch_id,
            'job_count': len(job_ids),
            'status': 'processing'
        }
        
    except Exception as e:
        logger.exception(f"Error processing batch job: {e}")
        return {'error': str(e)}

@functions_framework.cloud_event
def update_batch_status(cloud_event):
    """Background Cloud Function to update batch job status when individual jobs complete."""
    # Parse the PubSub message
    message_data = cloud_event.data.get('message', {}).get('data', '')
    if not message_data:
        logger.error("No message data received")
        return {'error': 'No message data received'}
    
    try:
        # Decode and parse the message
        import base64
        decoded_message = base64.b64decode(message_data).decode('utf-8')
        job_result = json.loads(decoded_message)
        
        # Get job details
        job_id = job_result.get('job_id')
        batch_id = job_result.get('batch_id')
        status = job_result.get('status')
        
        if not job_id or not batch_id:
            return {'error': 'Missing job_id or batch_id'}
        
        # Get batch job reference
        batch_ref = db.collection('batch_jobs').document(batch_id)
        batch_doc = batch_ref.get()
        
        if not batch_doc.exists:
            return {'error': f'Batch job {batch_id} not found'}
        
        # Get current batch data
        batch_data = batch_doc.to_dict()
        completed_count = batch_data.get('completed_count', 0)
        failed_count = batch_data.get('failed_count', 0)
        source_count = batch_data.get('source_count', 0)
        
        # Update counts based on job status
        if status == 'completed':
            completed_count += 1
        elif status == 'failed':
            failed_count += 1
        
        # Update batch job
        batch_update = {
            'completed_count': completed_count,
            'failed_count': failed_count,
            'updated_at': datetime.now().isoformat()
        }
        
        # Check if all jobs are done
        if completed_count + failed_count >= source_count:
            batch_update['status'] = 'completed'
            batch_update['completed_at'] = datetime.now().isoformat()
        
        batch_ref.update(batch_update)
        
        return {
            'batch_id': batch_id,
            'completed': completed_count,
            'failed': failed_count,
            'total': source_count
        }
        
    except Exception as e:
        logger.exception(f"Error updating batch status: {e}")
        return {'error': str(e)}