"""
FormatNormalizer Core Module

This module provides the main functionality for media format normalization.
"""

import os
import json
import uuid
import logging
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Union, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("formatnormalizer")

class MediaFormat:
    """Represents a media format with all its properties."""
    
    def __init__(self, 
                 container: str = "",
                 video_codec: str = "",
                 audio_codec: str = "",
                 width: int = 0,
                 height: int = 0,
                 frame_rate: float = 0,
                 duration: float = 0,
                 bitrate: int = 0,
                 file_size: int = 0):
        self.container = container
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.width = width
        self.height = height
        self.frame_rate = frame_rate
        self.duration = duration
        self.bitrate = bitrate
        self.file_size = file_size
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "container": self.container,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "duration": self.duration,
            "bitrate": self.bitrate,
            "file_size": self.file_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MediaFormat':
        """Create MediaFormat from dictionary."""
        return cls(
            container=data.get("container", ""),
            video_codec=data.get("video_codec", ""),
            audio_codec=data.get("audio_codec", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            frame_rate=data.get("frame_rate", 0),
            duration=data.get("duration", 0),
            bitrate=data.get("bitrate", 0),
            file_size=data.get("file_size", 0)
        )


class NormalizationResult:
    """Represents the result of a media normalization operation."""
    
    def __init__(self,
                 job_id: str,
                 source: str,
                 destination: str,
                 original_format: MediaFormat,
                 normalized_format: MediaFormat,
                 compression_ratio: float,
                 quality_metrics: Dict[str, float],
                 metadata_preserved: bool,
                 processing_time: float,
                 preset_used: str,
                 custom_params: Dict[str, Any]):
        self.job_id = job_id
        self.source = source
        self.destination = destination
        self.process_timestamp = datetime.now().isoformat()
        self.original_format = original_format
        self.normalized_format = normalized_format
        self.compression_ratio = compression_ratio
        self.quality_metrics = quality_metrics
        self.metadata_preserved = metadata_preserved
        self.processing_time = processing_time
        self.preset_used = preset_used
        self.custom_params = custom_params
        self.output_path = destination
        self.original_size = original_format.file_size
        self.new_size = normalized_format.file_size
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "job_id": self.job_id,
            "source": self.source,
            "destination": self.destination,
            "process_timestamp": self.process_timestamp,
            "original_format": self.original_format.to_dict(),
            "normalized_format": self.normalized_format.to_dict(),
            "compression_ratio": self.compression_ratio,
            "quality_metrics": self.quality_metrics,
            "metadata_preserved": self.metadata_preserved,
            "processing_time": self.processing_time,
            "preset_used": self.preset_used,
            "custom_params": self.custom_params
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NormalizationResult':
        """Create NormalizationResult from dictionary."""
        return cls(
            job_id=data.get("job_id", ""),
            source=data.get("source", ""),
            destination=data.get("destination", ""),
            original_format=MediaFormat.from_dict(data.get("original_format", {})),
            normalized_format=MediaFormat.from_dict(data.get("normalized_format", {})),
            compression_ratio=data.get("compression_ratio", 0),
            quality_metrics=data.get("quality_metrics", {}),
            metadata_preserved=data.get("metadata_preserved", False),
            processing_time=data.get("processing_time", 0),
            preset_used=data.get("preset_used", ""),
            custom_params=data.get("custom_params", {})
        )


class BatchJob:
    """Manages a batch media normalization job."""
    
    def __init__(self,
                 media_sources: List[str],
                 output_format: str,
                 preset: str,
                 preserve_metadata: bool = True,
                 destination_folder: str = ""):
        self.job_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.media_sources = media_sources
        self.output_format = output_format
        self.preset = preset
        self.preserve_metadata = preserve_metadata
        self.destination_folder = destination_folder
        self.status = {
            "total_count": len(media_sources),
            "processed_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "is_complete": False
        }
        self.results = {}
    
    def start(self) -> None:
        """Start processing the batch job."""
        logger.info(f"Starting batch job {self.job_id} with {len(self.media_sources)} files")
        
        # This would typically run in a background thread or separate process
        # For simplicity, we'll just process synchronously here
        normalizer = FormatNormalizer()
        
        for source in self.media_sources:
            try:
                # Determine destination path
                if self.destination_folder:
                    file_name = os.path.basename(source)
                    base_name = os.path.splitext(file_name)[0]
                    destination = os.path.join(
                        self.destination_folder, 
                        f"{base_name}.{self.output_format}"
                    )
                else:
                    # Use same directory as source if no destination specified
                    source_dir = os.path.dirname(source)
                    file_name = os.path.basename(source)
                    base_name = os.path.splitext(file_name)[0]
                    destination = os.path.join(
                        source_dir, 
                        f"{base_name}_normalized.{self.output_format}"
                    )
                
                # Process the file
                result = normalizer.normalize(
                    source=source,
                    output_format=self.output_format,
                    preset=self.preset,
                    preserve_metadata=self.preserve_metadata,
                    destination=destination
                )
                
                # Store the result
                self.results[source] = result
                self.status["success_count"] += 1
                
            except Exception as e:
                logger.error(f"Error processing {source}: {str(e)}")
                self.status["failed_count"] += 1
            
            self.status["processed_count"] += 1
        
        self.status["is_complete"] = True
        logger.info(f"Batch job {self.job_id} completed: {self.status}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current job status."""
        return self.status
    
    def get_results(self) -> Dict[str, NormalizationResult]:
        """Get job results."""
        if not self.status["is_complete"]:
            logger.warning("Attempting to get results before job completion")
        return self.results


class MediaAnalyzer:
    """Analyzes media properties using FFprobe."""
    
    def __init__(self):
        self.ffprobe_path = "ffprobe"  # Assumes ffprobe is in PATH
    
    def analyze(self, media_path: str, analysis_depth: str = "standard") -> MediaFormat:
        """
        Analyze media file and return format information.
        
        Args:
            media_path: Path to media file
            analysis_depth: Level of analysis detail ('basic', 'standard', 'detailed')
            
        Returns:
            MediaFormat object containing analysis results
        """
        logger.info(f"Analyzing media file: {media_path}")
        
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")
        
        # Get file size
        file_size = os.path.getsize(media_path)
        
        # Prepare FFprobe command for JSON output
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            media_path
        ]
        
        try:
            # Run FFprobe
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Extract format information
            format_info = data.get("format", {})
            streams = data.get("streams", [])
            
            # Initialize MediaFormat with default values
            media_format = MediaFormat(file_size=file_size)
            
            # Extract container format
            media_format.container = format_info.get("format_name", "")
            
            # Extract duration and bitrate
            if "duration" in format_info:
                media_format.duration = float(format_info["duration"])
            if "bit_rate" in format_info:
                media_format.bitrate = int(format_info["bit_rate"])
            
            # Process streams to find video and audio
            for stream in streams:
                codec_type = stream.get("codec_type", "")
                
                if codec_type == "video":
                    media_format.video_codec = stream.get("codec_name", "")
                    media_format.width = stream.get("width", 0)
                    media_format.height = stream.get("height", 0)
                    
                    # Calculate frame rate
                    if "r_frame_rate" in stream:
                        fps_parts = stream["r_frame_rate"].split('/')
                        if len(fps_parts) == 2 and int(fps_parts[1]) != 0:
                            media_format.frame_rate = float(int(fps_parts[0]) / int(fps_parts[1]))
                
                elif codec_type == "audio":
                    media_format.audio_codec = stream.get("codec_name", "")
            
            return media_format
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe analysis failed: {str(e)}")
            raise RuntimeError(f"Media analysis failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse FFprobe output: {str(e)}")
            raise RuntimeError(f"Failed to parse media analysis output: {str(e)}")


class FormatNormalizer:
    """
    Main class for normalizing media formats using FFmpeg.
    """
    
    def __init__(self, api_key: str = None, enable_drive: bool = False, drive_credentials: str = None):
        """
        Initialize the normalizer.
        
        Args:
            api_key: API key for Gemini API
            enable_drive: Whether to enable Google Drive integration
            drive_credentials: Path to Google Drive API credentials file
        """
        self.api_key = api_key
        self.enable_drive = enable_drive
        self.drive_credentials = drive_credentials
        self.ffmpeg_path = "ffmpeg"  # Assumes ffmpeg is in PATH
        self.analyzer = MediaAnalyzer()
        
        # Optional: Initialize Google API clients if enabled
        if self.enable_drive:
            # In a real implementation, we would initialize the Google Drive API client here
            logger.info("Google Drive integration enabled")
            if not os.path.exists(drive_credentials):
                logger.warning("Drive credentials file not found")
    
    def normalize(self,
                 source: str,
                 output_format: str,
                 preset: str = "standard",
                 custom_params: Dict[str, Any] = None,
                 preserve_metadata: bool = True,
                 destination: str = None) -> NormalizationResult:
        """
        Normalize a media file to the specified format.
        
        Args:
            source: Path or URL to source media
            output_format: Desired output format (e.g., "mp4", "wav")
            preset: Predefined conversion settings (e.g., "web", "broadcast")
            custom_params: Custom FFmpeg parameters
            preserve_metadata: Whether to preserve metadata
            destination: Output destination path
            
        Returns:
            NormalizationResult object with conversion results
        """
        start_time = datetime.now()
        job_id = f"norm_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting normalization job {job_id} for {source}")
        
        # If destination not specified, create one
        if not destination:
            source_dir = os.path.dirname(source)
            file_name = os.path.basename(source)
            base_name = os.path.splitext(file_name)[0]
            destination = os.path.join(
                source_dir, 
                f"{base_name}_normalized.{output_format}"
            )
        
        # Analyze source media
        original_format = self.analyzer.analyze(source)
        
        # Get preset parameters (this would normally load from a preset config)
        preset_params = self._get_preset(output_format, preset)
        if custom_params:
            # Merge custom parameters with preset
            preset_params.update(custom_params)
        
        # Prepare FFmpeg command
        cmd = [self.ffmpeg_path, "-i", source]
        
        # Add parameters based on preset
        for param, value in preset_params.items():
            if param.startswith("_"):  # Skip internal parameters
                continue
                
            if isinstance(value, bool):
                if value:  # Only add flag if True
                    cmd.append(f"-{param}")
            else:
                cmd.append(f"-{param}")
                cmd.append(str(value))
        
        # Add metadata preservation if requested
        if preserve_metadata:
            cmd.append("-map_metadata")
            cmd.append("0")
        
        # Add output path
        cmd.append(destination)
        
        # Execute FFmpeg command
        try:
            logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Analyze output file
            normalized_format = self.analyzer.analyze(destination)
            
            # Calculate compression ratio
            if original_format.file_size > 0 and normalized_format.file_size > 0:
                compression_ratio = original_format.file_size / normalized_format.file_size
            else:
                compression_ratio = 1.0
            
            # Calculate quality metrics (simplified - would be more sophisticated in real implementation)
            # In a real implementation, this would use tools like VMAF, PSNR, SSIM
            quality_metrics = {
                "psnr": 40.0,  # Placeholder
                "ssim": 0.95,  # Placeholder
                "vmaf": 90.0   # Placeholder
            }
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Create result object
            result = NormalizationResult(
                job_id=job_id,
                source=source,
                destination=destination,
                original_format=original_format,
                normalized_format=normalized_format,
                compression_ratio=compression_ratio,
                quality_metrics=quality_metrics,
                metadata_preserved=preserve_metadata,
                processing_time=processing_time,
                preset_used=preset,
                custom_params=custom_params or {}
            )
            
            logger.info(f"Normalization job {job_id} completed successfully")
            return result
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg processing failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise RuntimeError(f"Media normalization failed: {str(e)}")
    
    def create_batch_job(self,
                        media_sources: List[str],
                        output_format: str,
                        preset: str = "standard",
                        preserve_metadata: bool = True,
                        destination_folder: str = "") -> BatchJob:
        """Create a batch job for processing multiple files."""
        return BatchJob(
            media_sources=media_sources,
            output_format=output_format,
            preset=preset,
            preserve_metadata=preserve_metadata,
            destination_folder=destination_folder
        )
    
    def normalize_drive_folder(self,
                              folder_id: str,
                              output_format: str,
                              preset: str = "web",
                              recursive: bool = False,
                              file_types: List[str] = None) -> Dict[str, NormalizationResult]:
        """
        Process all media files in a Google Drive folder.
        
        This is a simplified placeholder implementation.
        In a real implementation, this would use the Google Drive API.
        """
        if not self.enable_drive:
            raise RuntimeError("Google Drive integration not enabled")
        
        # Placeholder implementation
        logger.info(f"Processing Google Drive folder {folder_id}")
        return {}
    
    def export_to_sheet(self,
                       results: Dict[str, NormalizationResult],
                       sheet_name: str,
                       create_new: bool = True) -> str:
        """
        Export normalization results to a Google Sheet.
        
        This is a simplified placeholder implementation.
        In a real implementation, this would use the Google Sheets API.
        """
        # Placeholder implementation
        sheet_id = f"sheet_{uuid.uuid4().hex[:8]}"
        logger.info(f"Exporting results to sheet {sheet_name} (ID: {sheet_id})")
        return sheet_id
    
    def _get_preset(self, format_type: str, preset_name: str) -> Dict[str, Any]:
        """
        Get preset parameters for a given format and preset name.
        
        In a real implementation, this would load from a database or config file.
        """
        # Default presets
        presets = {
            "mp4": {
                "web": {
                    "c:v": "libx264",
                    "c:a": "aac",
                    "b:v": "2M",
                    "b:a": "128k",
                    "preset": "medium",
                    "profile:v": "high",
                    "pix_fmt": "yuv420p"
                },
                "broadcast": {
                    "c:v": "libx264",
                    "c:a": "aac",
                    "b:v": "8M",
                    "b:a": "384k",
                    "preset": "slow",
                    "profile:v": "high"
                },
                "archive": {
                    "c:v": "libx265",
                    "c:a": "aac",
                    "crf": "18",
                    "preset": "slow",
                    "pix_fmt": "yuv420p10le"
                }
            },
            "mov": {
                "broadcast": {
                    "c:v": "prores_ks",
                    "profile:v": "3",
                    "vendor": "apl0",
                    "c:a": "pcm_s24le"
                }
            },
            "wav": {
                "standard": {
                    "c:a": "pcm_s24le",
                    "ar": "48000",
                    "ac": "2"
                }
            },
            "mp3": {
                "web": {
                    "c:a": "libmp3lame",
                    "b:a": "192k",
                    "ar": "44100"
                }
            }
        }
        
        # Use "standard" as default preset if the requested preset doesn't exist
        if format_type not in presets or preset_name not in presets[format_type]:
            logger.warning(f"Preset {preset_name} for format {format_type} not found, using defaults")
            return {"c:v": "copy", "c:a": "copy"}
        
        return presets[format_type][preset_name]


# Helper functions for presets
def get_preset(format_type: str, preset_name: str) -> Dict[str, Any]:
    """Get a preset by format and name."""
    normalizer = FormatNormalizer()
    return normalizer._get_preset(format_type, preset_name)

def list_presets(format_type: str = None) -> Dict[str, List[str]]:
    """List available presets, optionally filtered by format type."""
    # Simplified implementation - would be more robust in real code
    presets = {
        "mp4": ["web", "broadcast", "archive"],
        "mov": ["broadcast"],
        "wav": ["standard"],
        "mp3": ["web"]
    }
    
    if format_type:
        return {format_type: presets.get(format_type, [])}
    return presets

def add_preset(format_type: str, preset_name: str, params: Dict[str, Any]) -> bool:
    """Add or update a preset."""
    # Placeholder implementation
    logger.info(f"Adding preset {preset_name} for {format_type}")
    return True

def delete_preset(format_type: str, preset_name: str) -> bool:
    """Delete a preset."""
    # Placeholder implementation
    logger.info(f"Deleting preset {preset_name} for {format_type}")
    return True