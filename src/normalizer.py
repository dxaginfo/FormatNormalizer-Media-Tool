#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FormatNormalizer Core Module
============================

This module provides the core functionality for the FormatNormalizer tool,
handling media format conversion, optimization, and validation.
"""

import os
import json
import uuid
import subprocess
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import tempfile
import shutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FormatNormalizer:
    """
    Main class for media format normalization operations.
    
    This class provides methods to convert media files between formats,
    optimize encoding parameters, and validate outputs against specifications.
    """
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 temp_dir: Optional[str] = None,
                 gemini_api_key: Optional[str] = None):
        """
        Initialize the FormatNormalizer with configuration settings.
        
        Args:
            config_path: Path to configuration file
            temp_dir: Directory for temporary files
            gemini_api_key: API key for Gemini AI integration
        """
        self.config = self._load_config(config_path)
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.gemini_api_key = gemini_api_key or os.environ.get('GEMINI_API_KEY')
        
        # Verify FFmpeg is installed
        self._verify_ffmpeg()
        
        # Initialize presets
        self.presets = {
            "web": {
                "video": {"codec": "h264", "crf": 23, "preset": "medium"},
                "audio": {"codec": "aac", "bitrate": "128k"}
            },
            "social": {
                "video": {"codec": "h264", "crf": 20, "preset": "faster"},
                "audio": {"codec": "aac", "bitrate": "192k"}
            },
            "broadcast": {
                "video": {"codec": "prores", "profile": "standard"},
                "audio": {"codec": "pcm_s24le"}
            },
            "hq": {
                "video": {"codec": "h264", "crf": 18, "preset": "slow"},
                "audio": {"codec": "aac", "bitrate": "256k"}
            },
            "archive": {
                "video": {"codec": "ffv1", "level": 3},
                "audio": {"codec": "flac"}
            }
        }
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from a JSON file."""
        if not config_path:
            # Use default configuration
            return {
                "output_dir": "output",
                "max_threads": 4,
                "use_hardware_acceleration": True,
                "default_preset": "web",
                "validate_output": True
            }
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading configuration: {e}")
            # Fall back to default configuration
            return {
                "output_dir": "output",
                "max_threads": 4,
                "use_hardware_acceleration": True,
                "default_preset": "web",
                "validate_output": True
            }
    
    def _verify_ffmpeg(self) -> None:
        """Check if FFmpeg is installed and available."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=True
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"FFmpeg is not available: {e}")
            raise RuntimeError("FFmpeg is required but not found or not working properly")
    
    async def _analyze_media_with_gemini(self, media_path: str) -> Dict[str, Any]:
        """
        Use Gemini API to analyze media content and suggest optimal parameters.
        
        Args:
            media_path: Path to the media file
            
        Returns:
            Dictionary of recommended encoding parameters
        """
        if not self.gemini_api_key:
            logger.warning("Gemini API key not provided, skipping AI optimization")
            return {}
        
        # Get basic media information using FFprobe
        media_info = self._get_media_info(media_path)
        
        # Here we would call the Gemini API with the media information
        # For now, return a placeholder response
        logger.info(f"AI analysis would be performed here for {media_path}")
        
        # Placeholder for Gemini API integration
        # In a real implementation, we would use the Gemini API client
        # to analyze the media and get recommendations
        
        # Simulate AI analysis results
        ai_recommendations = {
            "recommended_codec": media_info.get("video_codec", "h264"),
            "quality_optimized_crf": 22 if media_info.get("has_motion", True) else 24,
            "encoding_speed": "medium",
            "notes": "AI optimization would provide specific recommendations based on content analysis"
        }
        
        return ai_recommendations
    
    def _get_media_info(self, media_path: str) -> Dict[str, Any]:
        """
        Extract technical metadata from media file using FFprobe.
        
        Args:
            media_path: Path to the media file
            
        Returns:
            Dictionary containing media file metadata
        """
        try:
            # Run FFprobe to get media information in JSON format
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    media_path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            
            probe_data = json.loads(result.stdout)
            
            # Extract relevant information
            info = {
                "format": probe_data.get("format", {}).get("format_name", ""),
                "duration": float(probe_data.get("format", {}).get("duration", 0)),
                "size": int(probe_data.get("format", {}).get("size", 0)),
                "streams": []
            }
            
            # Process stream information
            for stream in probe_data.get("streams", []):
                stream_type = stream.get("codec_type")
                stream_info = {
                    "index": stream.get("index"),
                    "codec": stream.get("codec_name"),
                    "codec_long": stream.get("codec_long_name"),
                    "type": stream_type
                }
                
                # Add stream-specific details
                if stream_type == "video":
                    stream_info.update({
                        "width": stream.get("width"),
                        "height": stream.get("height"),
                        "fps": eval(stream.get("r_frame_rate", "0/1")),
                        "bit_depth": stream.get("bits_per_raw_sample"),
                        "pixel_format": stream.get("pix_fmt")
                    })
                    info["video_codec"] = stream.get("codec_name")
                    
                elif stream_type == "audio":
                    stream_info.update({
                        "channels": stream.get("channels"),
                        "sample_rate": stream.get("sample_rate"),
                        "bit_depth": stream.get("bits_per_sample")
                    })
                
                info["streams"].append(stream_info)
            
            return info
        
        except (subprocess.SubprocessError, json.JSONDecodeError, IOError) as e:
            logger.error(f"Error getting media info for {media_path}: {e}")
            return {"error": str(e)}
    
    async def normalize(self, 
                 source: str, 
                 target_format: Optional[str] = None,
                 codec: Optional[str] = None,
                 preset: Optional[str] = None,
                 output_path: Optional[str] = None,
                 options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Normalize a media file to the specified format.
        
        Args:
            source: Path or URL to the source media file
            target_format: Desired output format (e.g., "mp4", "mov")
            codec: Desired codec (e.g., "h264", "prores")
            preset: Quality preset (e.g., "web", "broadcast")
            output_path: Custom output path
            options: Additional options for the normalization process
            
        Returns:
            Dictionary with normalization results and metadata
        """
        # Set default options
        options = options or {}
        preserve_metadata = options.get("preserveMetadata", True)
        enable_ai = options.get("enableAI", False)
        validate_output = options.get("validateOutput", True)
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create temporary working directory
        work_dir = os.path.join(self.temp_dir, f"normalize_{job_id}")
        os.makedirs(work_dir, exist_ok=True)
        
        try:
            # Step 1: Get source media information
            logger.info(f"Analyzing source media: {source}")
            source_info = self._get_media_info(source)
            
            # Step 2: If AI optimization is enabled, analyze with Gemini
            ai_recommendations = {}
            if enable_ai:
                logger.info("Using AI optimization")
                ai_recommendations = await self._analyze_media_with_gemini(source)
            
            # Step 3: Determine output format and parameters
            output_format = target_format or source_info.get("format").split(",")[0]
            
            # If preset is specified, use preset parameters
            encoding_params = {}
            if preset and preset in self.presets:
                encoding_params = self.presets[preset]
            
            # Override with explicit codec if provided
            if codec:
                for stream_type in encoding_params:
                    if "codec" in encoding_params[stream_type]:
                        encoding_params[stream_type]["codec"] = codec
            
            # Apply AI recommendations if available
            if ai_recommendations and "recommended_codec" in ai_recommendations:
                if "video" in encoding_params:
                    encoding_params["video"]["codec"] = ai_recommendations["recommended_codec"]
                    if "quality_optimized_crf" in ai_recommendations:
                        encoding_params["video"]["crf"] = ai_recommendations["quality_optimized_crf"]
            
            # Step 4: Set up the output path
            if not output_path:
                source_name = os.path.basename(source)
                source_base = os.path.splitext(source_name)[0]
                output_path = os.path.join(
                    self.config.get("output_dir", "output"),
                    f"{source_base}.{output_format}"
                )
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Step 5: Build FFmpeg command
            ffmpeg_cmd = self._build_ffmpeg_command(
                source, 
                output_path, 
                encoding_params, 
                preserve_metadata
            )
            
            # Step 6: Execute the normalization
            start_time = asyncio.get_event_loop().time()
            logger.info(f"Starting normalization with command: {' '.join(ffmpeg_cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            end_time = asyncio.get_event_loop().time()
            processing_time = end_time - start_time
            
            if process.returncode != 0:
                error_message = stderr.decode().strip()
                logger.error(f"FFmpeg error: {error_message}")
                return {
                    "success": False,
                    "error": error_message,
                    "job_id": job_id
                }
            
            # Step 7: Get output media information
            output_info = self._get_media_info(output_path)
            
            # Step 8: Validate output if requested
            validation_result = {"passed": True, "issues": []}
            if validate_output:
                validation_result = self._validate_output(output_path, output_info, encoding_params)
            
            # Step 9: Calculate performance metrics
            performance = {
                "processingTime": processing_time,
                "compressionRatio": source_info.get("size", 1) / max(output_info.get("size", 1), 1)
            }
            
            # Step 10: Return results
            return {
                "success": True,
                "job_id": job_id,
                "result": {
                    "uri": output_path,
                    "format": output_info.get("format", ""),
                    "codec": self._get_primary_codec(output_info),
                    "duration": output_info.get("duration", 0),
                    "fileSize": output_info.get("size", 0),
                    "resolution": self._get_resolution(output_info)
                },
                "metadata": {
                    "original": source_info if preserve_metadata else {},
                    "technical": output_info,
                    "transformations": self._get_transformations(source_info, output_info)
                },
                "performance": performance,
                "validation": validation_result
            }
            
        except Exception as e:
            logger.error(f"Error during normalization: {e}")
            return {
                "success": False,
                "error": str(e),
                "job_id": job_id
            }
        
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(work_dir)
            except OSError as e:
                logger.warning(f"Error cleaning up temporary directory: {e}")
    
    def _build_ffmpeg_command(self, 
                              input_path: str, 
                              output_path: str, 
                              encoding_params: Dict[str, Any],
                              preserve_metadata: bool) -> List[str]:
        """
        Build FFmpeg command for the normalization process.
        
        Args:
            input_path: Path to input file
            output_path: Path for output file
            encoding_params: Dictionary of encoding parameters
            preserve_metadata: Whether to preserve metadata
            
        Returns:
            List of command arguments for FFmpeg
        """
        cmd = ["ffmpeg", "-y", "-i", input_path]
        
        # Add global options
        if self.config.get("use_hardware_acceleration", False):
            # Try to use hardware acceleration if available
            cmd.extend(["-hwaccel", "auto"])
        
        # Add video encoding parameters
        video_params = encoding_params.get("video", {})
        if video_params:
            video_codec = video_params.get("codec")
            if video_codec:
                cmd.extend(["-c:v", video_codec])
            
            # Add codec-specific parameters
            if video_codec == "h264" or video_codec == "h265":
                # CRF-based encoding for H.264/H.265
                crf = video_params.get("crf", 23)
                preset = video_params.get("preset", "medium")
                cmd.extend(["-crf", str(crf), "-preset", preset])
                
            elif video_codec == "prores":
                # ProRes profile
                profile = video_params.get("profile", "standard")
                profile_map = {
                    "proxy": "0", "lt": "1", "standard": "2", 
                    "hq": "3", "4444": "4", "4444xq": "5"
                }
                cmd.extend(["-profile:v", profile_map.get(profile, "2")])
                
            elif video_codec == "vp9":
                # VP9 parameters
                crf = video_params.get("crf", 30)
                cmd.extend(["-crf", str(crf), "-b:v", "0"])
                
            elif video_codec == "av1":
                # AV1 parameters
                crf = video_params.get("crf", 30)
                cmd.extend(["-crf", str(crf), "-b:v", "0"])
        
        # Add audio encoding parameters
        audio_params = encoding_params.get("audio", {})
        if audio_params:
            audio_codec = audio_params.get("codec")
            if audio_codec:
                cmd.extend(["-c:a", audio_codec])
            
            # Add codec-specific parameters
            if audio_codec in ["aac", "mp3", "opus"]:
                bitrate = audio_params.get("bitrate", "128k")
                cmd.extend(["-b:a", bitrate])
        
        # Preserve metadata if requested
        if preserve_metadata:
            cmd.extend(["-map_metadata", "0"])
        
        # Add output path
        cmd.append(output_path)
        
        return cmd
    
    def _get_primary_codec(self, media_info: Dict[str, Any]) -> str:
        """Get the primary codec from media information."""
        for stream in media_info.get("streams", []):
            if stream.get("type") == "video":
                return stream.get("codec", "")
        return ""
    
    def _get_resolution(self, media_info: Dict[str, Any]) -> Dict[str, int]:
        """Get video resolution from media information."""
        for stream in media_info.get("streams", []):
            if stream.get("type") == "video":
                return {
                    "width": stream.get("width", 0),
                    "height": stream.get("height", 0)
                }
        return {"width": 0, "height": 0}
    
    def _get_transformations(self, 
                            source_info: Dict[str, Any], 
                            output_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compare source and output to determine what transformations were applied.
        
        Args:
            source_info: Source media information
            output_info: Output media information
            
        Returns:
            List of transformation descriptions
        """
        transformations = []
        
        # Check format change
        source_format = source_info.get("format", "").split(",")[0]
        output_format = output_info.get("format", "").split(",")[0]
        if source_format != output_format:
            transformations.append({
                "type": "format_conversion",
                "from": source_format,
                "to": output_format
            })
        
        # Check codec changes
        source_codecs = {}
        output_codecs = {}
        
        for stream in source_info.get("streams", []):
            stream_type = stream.get("type")
            codec = stream.get("codec")
            if stream_type and codec:
                source_codecs[stream_type] = codec
        
        for stream in output_info.get("streams", []):
            stream_type = stream.get("type")
            codec = stream.get("codec")
            if stream_type and codec:
                output_codecs[stream_type] = codec
        
        for stream_type in set(list(source_codecs.keys()) + list(output_codecs.keys())):
            source_codec = source_codecs.get(stream_type)
            output_codec = output_codecs.get(stream_type)
            
            if source_codec != output_codec:
                transformations.append({
                    "type": f"{stream_type}_codec_conversion",
                    "from": source_codec,
                    "to": output_codec
                })
        
        # Check resolution change
        source_resolution = self._get_resolution(source_info)
        output_resolution = self._get_resolution(output_info)
        
        if (source_resolution.get("width") != output_resolution.get("width") or
            source_resolution.get("height") != output_resolution.get("height")):
            transformations.append({
                "type": "resolution_change",
                "from": f"{source_resolution.get('width')}x{source_resolution.get('height')}",
                "to": f"{output_resolution.get('width')}x{output_resolution.get('height')}"
            })
        
        return transformations
    
    def _validate_output(self, 
                        output_path: str, 
                        output_info: Dict[str, Any],
                        encoding_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the output file against expected parameters.
        
        Args:
            output_path: Path to the output file
            output_info: Output media information
            encoding_params: Encoding parameters that were used
            
        Returns:
            Validation results dictionary
        """
        issues = []
        
        # Check if file exists
        if not os.path.exists(output_path):
            issues.append("Output file does not exist")
            return {"passed": False, "issues": issues}
        
        # Check if file is empty
        if os.path.getsize(output_path) == 0:
            issues.append("Output file is empty")
            return {"passed": False, "issues": issues}
        
        # Check if duration is valid
        if output_info.get("duration", 0) <= 0:
            issues.append("Output file has invalid duration")
        
        # Check codec compliance
        expected_video_codec = encoding_params.get("video", {}).get("codec")
        actual_video_codec = None
        
        for stream in output_info.get("streams", []):
            if stream.get("type") == "video":
                actual_video_codec = stream.get("codec")
                break
        
        if expected_video_codec and actual_video_codec and expected_video_codec != actual_video_codec:
            issues.append(f"Video codec mismatch: expected {expected_video_codec}, got {actual_video_codec}")
        
        # Check audio codec compliance
        expected_audio_codec = encoding_params.get("audio", {}).get("codec")
        actual_audio_codec = None
        
        for stream in output_info.get("streams", []):
            if stream.get("type") == "audio":
                actual_audio_codec = stream.get("codec")
                break
        
        if expected_audio_codec and actual_audio_codec and expected_audio_codec != actual_audio_codec:
            issues.append(f"Audio codec mismatch: expected {expected_audio_codec}, got {actual_audio_codec}")
        
        return {
            "passed": len(issues) == 0,
            "issues": issues
        }

class BatchProcessor:
    """
    Batch processing for multiple media files.
    """
    
    def __init__(self, normalizer: FormatNormalizer):
        """
        Initialize the batch processor.
        
        Args:
            normalizer: FormatNormalizer instance to use for processing
        """
        self.normalizer = normalizer
        self.jobs = []
    
    def add_file(self, 
                file_path: str, 
                target: Dict[str, Any] = None,
                options: Dict[str, Any] = None,
                output_path: str = None) -> None:
        """
        Add a file to the batch processing queue.
        
        Args:
            file_path: Path to the input file
            target: Target format specifications
            options: Processing options
            output_path: Custom output path
        """
        self.jobs.append({
            "file_path": file_path,
            "target": target or {},
            "options": options or {},
            "output_path": output_path
        })
    
    def add_directory(self, 
                     directory_path: str,
                     target: Dict[str, Any] = None,
                     options: Dict[str, Any] = None,
                     output_directory: str = None,
                     file_extensions: List[str] = None) -> None:
        """
        Add all files from a directory to the batch processing queue.
        
        Args:
            directory_path: Path to the input directory
            target: Target format specifications
            options: Processing options
            output_directory: Custom output directory
            file_extensions: List of file extensions to include
        """
        if file_extensions is None:
            file_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.wav', '.mp3', '.jpg', '.png']
        
        for root, _, files in os.walk(directory_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in file_extensions):
                    input_path = os.path.join(root, file)
                    
                    # Determine output path if specified
                    output_path = None
                    if output_directory:
                        rel_path = os.path.relpath(input_path, directory_path)
                        
                        # If target format is specified, change the extension
                        if target and 'format' in target:
                            base_path = os.path.splitext(rel_path)[0]
                            rel_path = f"{base_path}.{target['format']}"
                        
                        output_path = os.path.join(output_directory, rel_path)
                    
                    self.add_file(input_path, target, options, output_path)
    
    async def process(self) -> List[Dict[str, Any]]:
        """
        Process all files in the batch queue.
        
        Returns:
            List of results for each processed file
        """
        results = []
        
        for job in self.jobs:
            try:
                logger.info(f"Processing file: {job['file_path']}")
                
                result = await self.normalizer.normalize(
                    source=job["file_path"],
                    target_format=job["target"].get("format"),
                    codec=job["target"].get("codec"),
                    preset=job["target"].get("preset"),
                    output_path=job["output_path"],
                    options=job["options"]
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing {job['file_path']}: {e}")
                results.append({
                    "success": False,
                    "file_path": job["file_path"],
                    "error": str(e)
                })
        
        return results

# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FormatNormalizer: Media format conversion and standardization")
    parser.add_argument("input", help="Input file or directory")
    parser.add_argument("--output", "-o", help="Output file or directory")
    parser.add_argument("--format", "-f", help="Target format (e.g., mp4, mov)")
    parser.add_argument("--codec", "-c", help="Target codec (e.g., h264, prores)")
    parser.add_argument("--preset", "-p", choices=["web", "social", "broadcast", "hq", "archive"],
                        help="Quality preset")
    parser.add_argument("--recursive", "-r", action="store_true", help="Process directories recursively")
    parser.add_argument("--ai", "-a", action="store_true", help="Use AI optimization")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate output")
    
    args = parser.parse_args()
    
    # Run the normalization
    async def main():
        normalizer = FormatNormalizer()
        
        if os.path.isfile(args.input):
            # Process single file
            result = await normalizer.normalize(
                source=args.input,
                target_format=args.format,
                codec=args.codec,
                preset=args.preset,
                output_path=args.output,
                options={
                    "enableAI": args.ai,
                    "validateOutput": args.validate
                }
            )
            
            if result["success"]:
                print(f"Successfully normalized {args.input} to {result['result']['uri']}")
                print(f"Format: {result['result']['format']}, Codec: {result['result']['codec']}")
                print(f"Size: {result['result']['fileSize'] / (1024 * 1024):.2f} MB")
                print(f"Processing time: {result['performance']['processingTime']:.2f} seconds")
            else:
                print(f"Error normalizing {args.input}: {result.get('error', 'Unknown error')}")
        
        elif os.path.isdir(args.input):
            # Process directory
            batch = BatchProcessor(normalizer)
            
            batch.add_directory(
                args.input,
                target={
                    "format": args.format,
                    "codec": args.codec,
                    "preset": args.preset
                },
                options={
                    "enableAI": args.ai,
                    "validateOutput": args.validate
                },
                output_directory=args.output
            )
            
            results = await batch.process()
            
            successful = sum(1 for r in results if r.get("success", False))
            print(f"Processed {len(results)} files, {successful} successful")
        
        else:
            print(f"Input not found: {args.input}")
    
    asyncio.run(main())