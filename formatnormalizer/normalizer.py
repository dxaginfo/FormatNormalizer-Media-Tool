"""
FormatNormalizer main module for media format normalization
"""

import os
import json
import time
import logging
import subprocess
from typing import Dict, List, Optional, Union, Any
import uuid
import google.cloud.storage as storage
from google.cloud import firestore
import google.auth
import requests

from .models import NormalizationResult, BatchJob, MediaInfo
from .presets import PRESETS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("formatnormalizer")

class FormatNormalizer:
    """
    Core class for normalizing media formats using FFmpeg
    and Google Cloud services with Gemini API integration.
    """
    
    def __init__(self, api_key: str, enable_drive: bool = False, 
                 drive_credentials: Optional[str] = None):
        """
        Initialize the FormatNormalizer
        
        Args:
            api_key: API key for Gemini API
            enable_drive: Enable Google Drive integration
            drive_credentials: Path to Google Drive credentials JSON file
        """
        self.api_key = api_key
        self.enable_drive = enable_drive
        self.drive_credentials = drive_credentials
        self.gemini_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        
        # Initialize Firebase if credentials are available
        try:
            _, project = google.auth.default()
            self.db = firestore.Client(project=project)
            self.storage_client = storage.Client(project=project)
            self.firebase_available = True
        except Exception as e:
            logger.warning(f"Firebase initialization failed: {str(e)}")
            self.firebase_available = False
    
    def analyze(self, media_source: str, analysis_depth: str = "standard", 
                include_recommendations: bool = True) -> Dict[str, Any]:
        """
        Analyze media file and provide format details
        
        Args:
            media_source: Path, URL, or Drive ID of media file
            analysis_depth: Analysis detail level ('basic', 'standard', 'detailed')
            include_recommendations: Whether to include format recommendations
            
        Returns:
            Dictionary with media information and analysis
        """
        # Get media file locally if needed
        local_path = self._get_local_file(media_source)
        
        # Use FFprobe to get media information
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", local_path
        ]
        
        if analysis_depth == "detailed":
            cmd.extend(["-show_frames", "-read_intervals", "%+#10"])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        media_info = json.loads(result.stdout)
        
        # Process media information
        analysis = self._process_media_info(media_info)
        
        # Add recommendations if requested
        if include_recommendations:
            analysis["recommendations"] = self._get_format_recommendations(analysis)
        
        return analysis
    
    def normalize(self, source: str, output_format: str, preset: Optional[str] = None,
                  quality: Optional[str] = None, preserve_metadata: bool = True) -> NormalizationResult:
        """
        Normalize a single media file
        
        Args:
            source: Path, URL, or Drive ID of media file
            output_format: Target format (e.g., 'mp4', 'wav')
            preset: Optional preset name
            quality: Optional quality level ('low', 'medium', 'high')
            preserve_metadata: Whether to preserve metadata
            
        Returns:
            NormalizationResult object with result details
        """
        # Generate job ID
        job_id = f"norm_{uuid.uuid4().hex[:8]}"
        
        # Get media file locally if needed
        local_path = self._get_local_file(source)
        file_name = os.path.basename(local_path)
        base_name = os.path.splitext(file_name)[0]
        
        # Determine output path
        output_path = f"/tmp/{base_name}_normalized.{output_format}"
        
        # Get preset settings
        settings = self._get_preset_settings(preset, output_format, quality)
        
        # Start timer
        start_time = time.time()
        
        # Get original file size
        original_size = os.path.getsize(local_path)
        
        # Execute FFmpeg command
        ffmpeg_cmd = self._build_ffmpeg_command(local_path, output_path, settings, preserve_metadata)
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise Exception(f"Normalization failed: {result.stderr}")
        
        # End timer
        process_time = time.time() - start_time
        
        # Get new file size
        new_size = os.path.getsize(output_path)
        
        # Calculate size reduction
        size_reduction = ((original_size - new_size) / original_size) * 100 if original_size > 0 else 0
        
        # Create result object
        normalization_result = NormalizationResult(
            job_id=job_id,
            output_path=output_path,
            original_size=original_size,
            new_size=new_size,
            size_reduction=size_reduction,
            process_time=process_time,
            settings_used=settings
        )
        
        # Store job in Firestore if available
        if self.firebase_available:
            self._store_job(job_id, normalization_result)
        
        return normalization_result
    
    def create_batch_job(self, media_sources: List[str], output_format: str,
                        preset: Optional[str] = None, quality: Optional[str] = None,
                        preserve_metadata: bool = True, custom_settings: Optional[Dict] = None) -> BatchJob:
        """
        Create a batch job for processing multiple files
        
        Args:
            media_sources: List of media sources (paths, URLs, Drive IDs)
            output_format: Target format
            preset: Optional preset name
            quality: Optional quality level
            preserve_metadata: Whether to preserve metadata
            custom_settings: Optional custom settings dictionary
            
        Returns:
            BatchJob object for managing the batch process
        """
        # Generate batch job ID
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        
        # Create settings for the batch
        if custom_settings:
            settings = custom_settings
        else:
            settings = self._get_preset_settings(preset, output_format, quality)
        
        # Create batch job object
        batch_job = BatchJob(
            batch_id=batch_id,
            media_sources=media_sources,
            output_format=output_format,
            settings=settings,
            preserve_metadata=preserve_metadata,
            normalizer=self
        )
        
        # Store batch job in Firestore if available
        if self.firebase_available:
            self._store_batch_job(batch_id, batch_job)
        
        return batch_job
    
    def normalize_drive_folder(self, folder_id: str, output_format: str,
                              preset: Optional[str] = None, recursive: bool = False,
                              file_types: Optional[List[str]] = None) -> Dict[str, NormalizationResult]:
        """
        Process files in a Google Drive folder
        
        Args:
            folder_id: Google Drive folder ID
            output_format: Target format
            preset: Optional preset name
            recursive: Whether to process subfolders
            file_types: Optional list of file types to process
            
        Returns:
            Dictionary mapping file IDs to NormalizationResult objects
        """
        if not self.enable_drive:
            raise ValueError("Google Drive integration not enabled")
        
        # Get files from Google Drive folder
        files = self._get_drive_files(folder_id, recursive, file_types)
        
        # Process each file
        results = {}
        for file_id, file_info in files.items():
            try:
                result = self.normalize(
                    source=f"drive://{file_id}",
                    output_format=output_format,
                    preset=preset
                )
                results[file_id] = result
            except Exception as e:
                logger.error(f"Error processing file {file_id}: {str(e)}")
                results[file_id] = None
        
        return results
    
    def generate_report(self, results: Dict[str, NormalizationResult], 
                       report_format: str = "csv", save_to_drive: bool = False) -> str:
        """
        Generate a report for batch processing results
        
        Args:
            results: Dictionary of NormalizationResults
            report_format: Format for the report ('csv', 'json')
            save_to_drive: Whether to save to Google Drive
            
        Returns:
            Path or ID of the generated report
        """
        # Generate report file name
        report_path = f"/tmp/normalization_report_{uuid.uuid4().hex[:8]}.{report_format}"
        
        if report_format == "csv":
            # Create CSV report
            with open(report_path, 'w') as f:
                f.write("File ID,Original Size,New Size,Size Reduction (%),Process Time (s),Output Path\n")
                for file_id, result in results.items():
                    if result:
                        f.write(f"{file_id},{result.original_size},{result.new_size}," +
                               f"{result.size_reduction:.2f},{result.process_time:.2f},{result.output_path}\n")
                    else:
                        f.write(f"{file_id},Error,Error,Error,Error,Error\n")
        else:
            # Create JSON report
            report_data = {
                "timestamp": time.time(),
                "results": {
                    file_id: (result.to_dict() if result else {"error": "Processing failed"})
                    for file_id, result in results.items()
                }
            }
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
        
        # Save to Google Drive if requested
        if save_to_drive:
            if not self.enable_drive:
                raise ValueError("Google Drive integration not enabled")
            
            drive_id = self._upload_to_drive(report_path)
            return drive_id
        
        return report_path
    
    def _get_local_file(self, source: str) -> str:
        """Get local file path from source (download if needed)"""
        if os.path.exists(source):
            return source
        
        if source.startswith("http://") or source.startswith("https://"):
            # Download from URL
            local_path = f"/tmp/{uuid.uuid4().hex}"
            response = requests.get(source, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return local_path
        
        if source.startswith("drive://") and self.enable_drive:
            # Download from Google Drive
            drive_id = source.replace("drive://", "")
            local_path = f"/tmp/{uuid.uuid4().hex}"
            
            # Download logic here (using Drive API)
            # ...
            
            return local_path
        
        if source.startswith("gs://") and self.firebase_available:
            # Download from Google Cloud Storage
            bucket_name, blob_path = source[5:].split("/", 1)
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            local_path = f"/tmp/{uuid.uuid4().hex}"
            blob.download_to_filename(local_path)
            
            return local_path
        
        raise ValueError(f"Unsupported source format: {source}")
    
    def _process_media_info(self, media_info: Dict) -> Dict:
        """Process FFprobe media information into structured analysis"""
        analysis = {
            "format": {
                "name": media_info.get("format", {}).get("format_name", "unknown"),
                "long_name": media_info.get("format", {}).get("format_long_name", "unknown"),
                "duration": float(media_info.get("format", {}).get("duration", 0)),
                "size": int(media_info.get("format", {}).get("size", 0)),
                "bit_rate": int(media_info.get("format", {}).get("bit_rate", 0)),
            },
            "streams": []
        }
        
        # Process streams
        for stream in media_info.get("streams", []):
            stream_type = stream.get("codec_type")
            stream_info = {
                "index": stream.get("index"),
                "codec_name": stream.get("codec_name"),
                "codec_long_name": stream.get("codec_long_name"),
                "codec_type": stream_type,
            }
            
            # Add video-specific info
            if stream_type == "video":
                stream_info.update({
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                    "frame_rate": self._calculate_frame_rate(stream),
                    "bit_rate": int(stream.get("bit_rate", 0)),
                    "pix_fmt": stream.get("pix_fmt"),
                    "color_space": stream.get("color_space"),
                    "color_transfer": stream.get("color_transfer"),
                    "color_primaries": stream.get("color_primaries"),
                })
            
            # Add audio-specific info
            elif stream_type == "audio":
                stream_info.update({
                    "sample_rate": int(stream.get("sample_rate", 0)),
                    "channels": stream.get("channels"),
                    "channel_layout": stream.get("channel_layout"),
                    "bit_rate": int(stream.get("bit_rate", 0)),
                    "sample_fmt": stream.get("sample_fmt"),
                })
            
            analysis["streams"].append(stream_info)
        
        return analysis
    
    def _calculate_frame_rate(self, stream: Dict) -> float:
        """Calculate frame rate from stream information"""
        if "r_frame_rate" in stream:
            parts = stream["r_frame_rate"].split("/")
            if len(parts) == 2 and int(parts[1]) > 0:
                return float(int(parts[0]) / int(parts[1]))
        
        if "avg_frame_rate" in stream:
            parts = stream["avg_frame_rate"].split("/")
            if len(parts) == 2 and int(parts[1]) > 0:
                return float(int(parts[0]) / int(parts[1]))
        
        return 0.0
    
    def _get_format_recommendations(self, analysis: Dict) -> Dict:
        """Get format recommendations based on analysis and Gemini API"""
        try:
            # Prepare the prompt for Gemini API
            prompt = f"""
            You are a media format optimization expert. Based on the following media analysis,
            recommend the most appropriate target format and optimization settings to balance
            quality and file size for general use. Consider codec efficiency, compatibility,
            and quality preservation.
            
            Media Analysis:
            {json.dumps(analysis, indent=2)}
            
            Provide recommendations in this JSON format:
            {{
                "recommended_format": "format_name",
                "recommended_video_codec": "codec_name",
                "recommended_audio_codec": "codec_name",
                "recommended_settings": {{
                    "setting1": "value1",
                    "setting2": "value2"
                }},
                "rationale": "Explanation of recommendations"
            }}
            """
            
            # Call Gemini API
            response = requests.post(
                f"{self.gemini_endpoint}?key={self.api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 1024,
                    }
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract the recommendation
            text_result = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Extract JSON part
            start_idx = text_result.find('{')
            end_idx = text_result.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text_result[start_idx:end_idx]
                return json.loads(json_str)
            
            raise ValueError("Could not extract JSON recommendation from Gemini API response")
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}")
            return {
                "error": "Failed to generate recommendations",
                "reason": str(e)
            }
    
    def _get_preset_settings(self, preset_name: Optional[str], output_format: str, 
                           quality: Optional[str]) -> Dict:
        """Get preset settings based on name, format, and quality"""
        # Start with default settings
        settings = {
            "video_codec": "libx264",
            "audio_codec": "aac",
            "video_bitrate": "2M",
            "audio_bitrate": "128k",
            "preset": "medium",
            "crf": 23,
        }
        
        # Update from preset if specified
        if preset_name and preset_name in PRESETS:
            settings.update(PRESETS[preset_name])
        
        # Override based on output format
        if output_format == "mp4":
            settings.update({
                "video_codec": "libx264",
                "audio_codec": "aac",
            })
        elif output_format == "webm":
            settings.update({
                "video_codec": "libvpx-vp9",
                "audio_codec": "libopus",
            })
        elif output_format == "wav":
            settings.update({
                "audio_codec": "pcm_s16le",
            })
        elif output_format == "mp3":
            settings.update({
                "audio_codec": "libmp3lame",
            })
        
        # Adjust for quality
        if quality == "low":
            settings.update({
                "crf": 28,
                "audio_bitrate": "96k",
                "preset": "faster",
            })
        elif quality == "high":
            settings.update({
                "crf": 18,
                "audio_bitrate": "192k",
                "preset": "slow",
            })
        
        return settings
    
    def _build_ffmpeg_command(self, input_path: str, output_path: str, 
                            settings: Dict, preserve_metadata: bool) -> List[str]:
        """Build FFmpeg command line based on settings"""
        cmd = ["ffmpeg", "-i", input_path]
        
        # Add video settings if applicable
        if "video_codec" in settings:
            cmd.extend(["-c:v", settings["video_codec"]])
            
            # Add codec-specific settings
            if settings["video_codec"] == "libx264":
                cmd.extend(["-preset", settings.get("preset", "medium")])
                cmd.extend(["-crf", str(settings.get("crf", 23))])
            
            elif settings["video_codec"] == "libvpx-vp9":
                cmd.extend(["-b:v", settings.get("video_bitrate", "2M")])
                cmd.extend(["-deadline", "good"])
        
        # Add audio settings if applicable
        if "audio_codec" in settings:
            cmd.extend(["-c:a", settings["audio_codec"]])
            
            # Add codec-specific settings
            if settings["audio_codec"] in ["aac", "libmp3lame", "libopus"]:
                cmd.extend(["-b:a", settings.get("audio_bitrate", "128k")])
        
        # Preserve metadata if requested
        if preserve_metadata:
            cmd.extend(["-map_metadata", "0"])
        
        # Additional settings
        if "scale" in settings:
            cmd.extend(["-vf", f"scale={settings['scale']}"])
        
        # Add output file
        cmd.append(output_path)
        
        return cmd
    
    def _store_job(self, job_id: str, result: NormalizationResult) -> None:
        """Store job in Firestore"""
        if not self.firebase_available:
            return
        
        job_ref = self.db.collection("normalization_jobs").document(job_id)
        job_ref.set(result.to_dict())
    
    def _store_batch_job(self, batch_id: str, batch_job: BatchJob) -> None:
        """Store batch job in Firestore"""
        if not self.firebase_available:
            return
        
        batch_ref = self.db.collection("batch_jobs").document(batch_id)
        batch_ref.set({
            "batch_id": batch_id,
            "media_sources": batch_job.media_sources,
            "output_format": batch_job.output_format,
            "settings": batch_job.settings,
            "preserve_metadata": batch_job.preserve_metadata,
            "status": "created",
            "created_at": firestore.SERVER_TIMESTAMP,
        })
    
    def _get_drive_files(self, folder_id: str, recursive: bool, 
                        file_types: Optional[List[str]]) -> Dict[str, Dict]:
        """Get files from Google Drive folder"""
        # This would use the Google Drive API
        # Placeholder implementation
        return {}
    
    def _upload_to_drive(self, file_path: str) -> str:
        """Upload file to Google Drive"""
        # This would use the Google Drive API
        # Placeholder implementation
        return "drive_file_id"