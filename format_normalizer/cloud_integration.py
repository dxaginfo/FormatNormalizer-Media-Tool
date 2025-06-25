import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from google.cloud import storage
from google.cloud import firestore

class CloudStorageManager:
    """Manages Google Cloud Storage operations for media files."""
    
    def __init__(self, bucket_name: str, credentials_path: Optional[str] = None):
        """Initialize the Cloud Storage manager.
        
        Args:
            bucket_name: Name of the GCS bucket to use
            credentials_path: Path to GCP credentials JSON file. If None, uses application default credentials.
        """
        self.bucket_name = bucket_name
        
        if credentials_path:
            self.storage_client = storage.Client.from_service_account_json(credentials_path)
        else:
            self.storage_client = storage.Client()
            
        self.bucket = self.storage_client.bucket(bucket_name)
    
    async def upload_file(self, source_path: str, destination_blob_name: str) -> str:
        """Upload a file to Google Cloud Storage.
        
        Args:
            source_path: Path to the local file to upload
            destination_blob_name: Name of the destination blob in GCS
            
        Returns:
            Public URL of the uploaded file
        """
        # Create a blob object for the destination
        blob = self.bucket.blob(destination_blob_name)
        
        # Run the upload in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: blob.upload_from_filename(source_path))
        
        # Make the blob publicly accessible
        blob.make_public()
        
        return blob.public_url
    
    async def download_file(self, source_blob_name: str, destination_path: str) -> str:
        """Download a file from Google Cloud Storage.
        
        Args:
            source_blob_name: Name of the source blob in GCS
            destination_path: Path to save the downloaded file locally
            
        Returns:
            Path to the downloaded file
        """
        # Create a blob object for the source
        blob = self.bucket.blob(source_blob_name)
        
        # Run the download in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: blob.download_to_filename(destination_path))
        
        return destination_path
    
    async def list_files(self, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in the GCS bucket with an optional prefix.
        
        Args:
            prefix: Optional prefix to filter blobs
            
        Returns:
            List of blob information dictionaries
        """
        blobs = self.bucket.list_blobs(prefix=prefix)
        
        result = []
        for blob in blobs:
            result.append({
                'name': blob.name,
                'size': blob.size,
                'updated': blob.updated,
                'url': blob.public_url if blob.public else None
            })
            
        return result
    
    async def delete_file(self, blob_name: str) -> bool:
        """Delete a file from Google Cloud Storage.
        
        Args:
            blob_name: Name of the blob to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        # Create a blob object
        blob = self.bucket.blob(blob_name)
        
        # Run the deletion in a thread pool to avoid blocking
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, blob.delete)
            return True
        except Exception as e:
            logging.error(f"Error deleting blob {blob_name}: {e}")
            return False

class FirestoreManager:
    """Manages Firestore operations for job metadata and tracking."""
    
    def __init__(self, collection_name: str = 'normalization_jobs', credentials_path: Optional[str] = None):
        """Initialize the Firestore manager.
        
        Args:
            collection_name: Name of the Firestore collection to use
            credentials_path: Path to GCP credentials JSON file. If None, uses application default credentials.
        """
        self.collection_name = collection_name
        
        if credentials_path:
            self.db = firestore.Client.from_service_account_json(credentials_path)
        else:
            self.db = firestore.Client()
    
    async def create_job(self, job_data: Dict[str, Any]) -> str:
        """Create a new normalization job in Firestore.
        
        Args:
            job_data: Dictionary containing job data
            
        Returns:
            ID of the created job document
        """
        # Add created timestamp if not present
        if 'created_at' not in job_data:
            job_data['created_at'] = firestore.SERVER_TIMESTAMP
            
        # Add status if not present
        if 'status' not in job_data:
            job_data['status'] = 'pending'
        
        # Create a new document with auto-generated ID
        doc_ref = self.db.collection(self.collection_name).document()
        
        # Run the set operation in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: doc_ref.set(job_data))
        
        return doc_ref.id
    
    async def update_job(self, job_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an existing normalization job in Firestore.
        
        Args:
            job_id: ID of the job document to update
            update_data: Dictionary containing fields to update
            
        Returns:
            True if update was successful, False otherwise
        """
        # Add updated timestamp
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        # Get the document reference
        doc_ref = self.db.collection(self.collection_name).document(job_id)
        
        # Run the update operation in a thread pool to avoid blocking
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: doc_ref.update(update_data))
            return True
        except Exception as e:
            logging.error(f"Error updating job {job_id}: {e}")
            return False
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a normalization job from Firestore.
        
        Args:
            job_id: ID of the job document to retrieve
            
        Returns:
            Dictionary containing job data, or None if not found
        """
        # Get the document reference
        doc_ref = self.db.collection(self.collection_name).document(job_id)
        
        # Run the get operation in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, doc_ref.get)
        
        if doc.exists:
            return doc.to_dict()
        else:
            return None
    
    async def list_jobs(self, filters: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List normalization jobs from Firestore with optional filters.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            limit: Maximum number of jobs to return
            
        Returns:
            List of job data dictionaries
        """
        # Start with the collection reference
        query = self.db.collection(self.collection_name)
        
        # Apply filters if provided
        if filters:
            for field, value in filters.items():
                query = query.where(field, '==', value)
        
        # Apply limit and order by created timestamp
        query = query.order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
        
        # Run the query in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        docs = await loop.run_in_executor(None, query.stream)
        
        # Convert documents to dictionaries and add IDs
        result = []
        for doc in docs:
            job_data = doc.to_dict()
            job_data['id'] = doc.id
            result.append(job_data)
            
        return result
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a normalization job from Firestore.
        
        Args:
            job_id: ID of the job document to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        # Get the document reference
        doc_ref = self.db.collection(self.collection_name).document(job_id)
        
        # Run the delete operation in a thread pool to avoid blocking
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, doc_ref.delete)
            return True
        except Exception as e:
            logging.error(f"Error deleting job {job_id}: {e}")
            return False