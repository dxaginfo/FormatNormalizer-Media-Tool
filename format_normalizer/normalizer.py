import os
import json
import asyncio
import subprocess
import logging
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .ai_analyzer import AIAnalysisModule

class FormatNormalizer:
    """Core class for media format normalization and conversion."""
    
    def __init__(self, ai_api_key: Optional[str] = None, temp_dir: Optional[str] = None):
        """Initialize the FormatNormalizer.
        
        Args:
            ai_api_key: API key for Gemini AI integration. If None, tries to get from environment variable.
            temp_dir: Directory for temporary files. If None, uses system default temp directory.
        """
        self.ai_analyzer = AIAnalysisModule(api_key=ai_api_key)
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.logger = logging.getLogger(__name__)
    
    async def normalize(self, source_path: str, output_path: str, target_format: Dict[str, Any],
                      preset: str = "standard", enable_ai: bool = False, validate_output: bool = True) -> Dict[str, Any]:
        """Normalize a media file to the target format.
        
        Args:
            source_path: Path to the source media file
            output_path: Path where the normalized file should be saved
            target_format: Dictionary specifying the target format requirements
            preset: Quality preset (web, social, broadcast, archive, mobile)
            enable_ai: Whether to use AI for content-aware optimizations
            validate_output: Whether to validate the output after conversion
            
        Returns:
            Dictionary containing normalization results and metadata
        """
        # Start tracking processing time
        start_time = datetime.now()
        
        # 1. Analyze source media
        source_metadata = await self._analyze_media(source_path)
        
        # 2. Prepare target format parameters
        format_params = self._prepare_format_parameters(target_format, preset)
        
        # 3. Get AI recommendations if enabled
        if enable_ai:
            ai_analysis = await self.ai_analyzer.analyze_content(
                media_path=source_path,
                media_metadata=source_metadata,
                target_format=format_params
            )
            format_params = self._apply_ai_recommendations(format_params, ai_analysis)
        else:
            ai_analysis = None
        
        # 4. Perform the format conversion
        conversion_result = await self._convert_media(
            source_path=source_path,
            output_path=output_path,
            format_params=format_params,
            source_metadata=source_metadata
        )
        
        # 5. Analyze the output media
        if os.path.exists(output_path):
            output_metadata = await self._analyze_media(output_path)
        else:
            raise RuntimeError(f"Conversion failed: Output file not found at {output_path}")
        
        # 6. Validate the output if requested
        validation_results = None
        if validate_output:
            validation_results = await self._validate_output(
                source_metadata=source_metadata,
                output_metadata=output_metadata,
                target_format=format_params
            )
        
        # Calculate processing time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Prepare the result object
        result = {
            "result": {
                "uri": output_path,
                "format": output_metadata.get("format", {}).get("format_name", ""),
                "codec": self._get_codec_info(output_metadata),
                "duration": output_metadata.get("format", {}).get("duration", 0),
                "fileSize": os.path.getsize(output_path),
                "resolution": self._get_resolution(output_metadata)
            },
            "metadata": {
                "original": source_metadata,
                "technical": output_metadata,
                "transformations": conversion_result.get("transformations", [])
            },
            "performance": {
                "processingTime": processing_time,
                "qualityMetrics": self._calculate_quality_metrics(source_metadata, output_metadata),
                "compressionRatio": self._calculate_compression_ratio(source_path, output_path)
            }
        }
        
        # Add validation results if available
        if validation_results:
            result["validation"] = validation_results
        
        # Add AI analysis if available
        if ai_analysis:
            result["ai_analysis"] = ai_analysis
        
        return result
    
    async def _analyze_media(self, media_path: str) -> Dict[str, Any]:
        """Analyze media file to get technical metadata using FFprobe.
        
        Args:
            media_path: Path to the media file to analyze
            
        Returns:
            Dictionary containing detailed media metadata
        """
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")
        
        # Prepare FFprobe command
        ffprobe_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            media_path
        ]
        
        # Run FFprobe as a subprocess
        try:
            # Run in an executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(ffprobe_cmd, capture_output=True, text=True)
            )
            
            if process.returncode != 0:
                self.logger.error(f"FFprobe error: {process.stderr}")
                raise RuntimeError(f"FFprobe failed with return code {process.returncode}: {process.stderr}")
            
            # Parse the JSON output
            metadata = json.loads(process.stdout)
            return metadata
        
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing FFprobe output: {e}")
            raise RuntimeError(f"Invalid FFprobe output: {e}")
        except Exception as e:
            self.logger.error(f"Error analyzing media with FFprobe: {e}")
            raise RuntimeError(f"Media analysis failed: {e}")
    
    def _prepare_format_parameters(self, target_format: Dict[str, Any], preset: str) -> Dict[str, Any]:
        """Prepare format parameters based on target format and preset.
        
        Args:
            target_format: Dictionary specifying the target format
            preset: Quality preset name
            
        Returns:
            Dictionary with detailed format parameters for conversion
        """
        # Get base format info
        format_type = target_format.get("format", "mp4").lower()
        codec = target_format.get("codec", "")
        
        # Auto-select codec if not specified
        if not codec:
            codec = self._get_default_codec(format_type)
        
        # Build parameters dictionary
        params = {
            "format": format_type,
            "codec": codec,
            "preset": preset,
            "parameters": {}
        }
        
        # Apply preset-specific parameters
        if preset == "web":
            params["parameters"] = {
                "video": {
                    "crf": 23 if codec in ["h264", "libx264"] else 28,
                    "preset": "medium",
                    "movflags": "+faststart"
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "128k"
                }
            }
        elif preset == "social":
            params["parameters"] = {
                "video": {
                    "crf": 20 if codec in ["h264", "libx264"] else 25,
                    "preset": "medium",
                    "movflags": "+faststart",
                    "maxrate": "4M",
                    "bufsize": "8M"
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "192k"
                }
            }
        elif preset == "broadcast":
            params["parameters"] = {
                "video": {
                    "profile": "3" if codec == "prores" else "high",
                    "level": "5.1" if codec in ["h264", "libx264"] else None,
                    "preset": "slow" if codec in ["h264", "libx264", "h265", "libx265"] else None,
                    "pix_fmt": "yuv422p10le" if codec == "prores" else "yuv420p"
                },
                "audio": {
                    "codec": "pcm_s24le" if format_type in ["mov", "mxf"] else "aac",
                    "sample_rate": "48000"
                }
            }
        elif preset == "archive":
            params["parameters"] = {
                "video": {
                    "profile": "4444" if codec == "prores" else "high",
                    "pix_fmt": "yuv444p10le" if codec == "prores" else "yuv420p",
                    "qscale": "1" if codec == "mjpeg" else None
                },
                "audio": {
                    "codec": "pcm_s24le",
                    "sample_rate": "48000"
                }
            }
        elif preset == "mobile":
            params["parameters"] = {
                "video": {
                    "crf": 26 if codec in ["h264", "libx264"] else 30,
                    "preset": "medium",
                    "movflags": "+faststart",
                    "maxrate": "2M",
                    "bufsize": "4M"
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "96k"
                }
            }
        else:  # standard preset
            params["parameters"] = {
                "video": {
                    "crf": 23 if codec in ["h264", "libx264"] else 28,
                    "preset": "medium"
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "192k"
                }
            }
        
        # Add any additional parameters from target_format
        if "parameters" in target_format and isinstance(target_format["parameters"], dict):
            for key, value in target_format["parameters"].items():
                if key in params["parameters"]:
                    params["parameters"][key].update(value)
                else:
                    params["parameters"][key] = value
        
        return params
    
    def _apply_ai_recommendations(self, format_params: Dict[str, Any], ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Apply AI recommendations to format parameters.
        
        Args:
            format_params: Base format parameters
            ai_analysis: AI analysis results containing recommendations
            
        Returns:
            Updated format parameters with AI recommendations applied
        """
        # Get encoding recommendations from AI analysis
        recommendations = ai_analysis.get("encoding_recommendations", {})
        
        if not recommendations:
            return format_params
        
        # Apply codec parameters
        if "codec_parameters" in recommendations and isinstance(recommendations["codec_parameters"], dict):
            for key, value in recommendations["codec_parameters"].items():
                if "video" in format_params["parameters"]:
                    format_params["parameters"]["video"][key] = value
        
        # Apply bitrate strategy
        if "bitrate_strategy" in recommendations and isinstance(recommendations["bitrate_strategy"], dict):
            strategy = recommendations["bitrate_strategy"]
            strategy_type = strategy.get("type")
            strategy_value = strategy.get("value")
            
            if strategy_type and strategy_value and "video" in format_params["parameters"]:
                if strategy_type == "CRF":
                    format_params["parameters"]["video"]["crf"] = strategy_value
                elif strategy_type == "CBR":
                    format_params["parameters"]["video"]["bitrate"] = strategy_value
                    format_params["parameters"]["video"]["minrate"] = strategy_value
                    format_params["parameters"]["video"]["maxrate"] = strategy_value
                    format_params["parameters"]["video"]["bufsize"] = f"{int(strategy_value.replace('k', '000')) * 2}k"
                elif strategy_type == "VBR":
                    format_params["parameters"]["video"]["bitrate"] = strategy_value
        
        # Apply additional FFmpeg options
        if "ffmpeg_options" in recommendations and isinstance(recommendations["ffmpeg_options"], list):
            if "ffmpeg_options" not in format_params["parameters"]:
                format_params["parameters"]["ffmpeg_options"] = []
            
            format_params["parameters"]["ffmpeg_options"].extend(recommendations["ffmpeg_options"])
        
        return format_params
    
    async def _convert_media(self, source_path: str, output_path: str, format_params: Dict[str, Any], 
                          source_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert media to the target format using FFmpeg.
        
        Args:
            source_path: Path to the source media file
            output_path: Path where the converted file should be saved
            format_params: Conversion parameters dictionary
            source_metadata: Metadata of the source media
            
        Returns:
            Dictionary containing conversion results
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Build FFmpeg command
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", source_path]
        
        # Add video codec parameters if source has video
        has_video = any(stream.get("codec_type") == "video" for stream in source_metadata.get("streams", []))
        if has_video and "video" in format_params["parameters"]:
            video_params = format_params["parameters"]["video"]
            codec = format_params["codec"]
            
            # Add video codec
            if codec == "h264":
                ffmpeg_cmd.extend(["-c:v", "libx264"])
            elif codec == "h265" or codec == "hevc":
                ffmpeg_cmd.extend(["-c:v", "libx265"])
            elif codec == "prores":
                ffmpeg_cmd.extend(["-c:v", "prores_ks"])
            elif codec == "av1":
                ffmpeg_cmd.extend(["-c:v", "libaom-av1"])
            elif codec == "vp9":
                ffmpeg_cmd.extend(["-c:v", "libvpx-vp9"])
            else:
                ffmpeg_cmd.extend(["-c:v", codec])
            
            # Add other video parameters
            for key, value in video_params.items():
                if value is not None:
                    if key == "crf":
                        ffmpeg_cmd.extend(["-crf", str(value)])
                    elif key == "preset":
                        ffmpeg_cmd.extend(["-preset", str(value)])
                    elif key == "profile":
                        if codec == "prores":
                            ffmpeg_cmd.extend(["-profile:v", str(value)])
                        else:
                            ffmpeg_cmd.extend(["-profile:v", str(value)])
                    elif key == "level" and codec in ["h264", "libx264", "h265", "libx265"]:
                        ffmpeg_cmd.extend(["-level", str(value)])
                    elif key == "pix_fmt":
                        ffmpeg_cmd.extend(["-pix_fmt", str(value)])
                    elif key == "maxrate":
                        ffmpeg_cmd.extend(["-maxrate", str(value)])
                    elif key == "minrate":
                        ffmpeg_cmd.extend(["-minrate", str(value)])
                    elif key == "bufsize":
                        ffmpeg_cmd.extend(["-bufsize", str(value)])
                    elif key == "qscale":
                        ffmpeg_cmd.extend(["-qscale:v", str(value)])
                    elif key == "bitrate":
                        ffmpeg_cmd.extend(["-b:v", str(value)])
                    elif key == "movflags" and format_params["format"] in ["mp4", "mov"]:
                        ffmpeg_cmd.extend(["-movflags", str(value)])
        
        # Add audio codec parameters if source has audio
        has_audio = any(stream.get("codec_type") == "audio" for stream in source_metadata.get("streams", []))
        if has_audio and "audio" in format_params["parameters"]:
            audio_params = format_params["parameters"]["audio"]
            
            # Add audio codec
            if "codec" in audio_params:
                ffmpeg_cmd.extend(["-c:a", audio_params["codec"]])
            
            # Add other audio parameters
            for key, value in audio_params.items():
                if value is not None and key != "codec":
                    if key == "bitrate":
                        ffmpeg_cmd.extend(["-b:a", str(value)])
                    elif key == "sample_rate":
                        ffmpeg_cmd.extend(["-ar", str(value)])
                    elif key == "channels":
                        ffmpeg_cmd.extend(["-ac", str(value)])
        
        # Add any additional custom FFmpeg options
        if "ffmpeg_options" in format_params["parameters"]:
            for option in format_params["parameters"]["ffmpeg_options"]:
                ffmpeg_cmd.append(str(option))
        
        # Add output format if specified
        if format_params["format"]:
            ffmpeg_cmd.extend(["-f", format_params["format"]])
        
        # Add output path
        ffmpeg_cmd.append(output_path)
        
        # Log the FFmpeg command
        self.logger.info(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")
        
        # Run FFmpeg as a subprocess
        try:
            # Run in an executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            )
            
            if process.returncode != 0:
                self.logger.error(f"FFmpeg error: {process.stderr}")
                raise RuntimeError(f"FFmpeg failed with return code {process.returncode}: {process.stderr}")
            
            # Parse the transformations from the FFmpeg output
            transformations = self._parse_ffmpeg_output(process.stderr)
            
            return {
                "success": True,
                "command": ' '.join(ffmpeg_cmd),
                "transformations": transformations
            }
        
        except Exception as e:
            self.logger.error(f"Error converting media with FFmpeg: {e}")
            raise RuntimeError(f"Media conversion failed: {e}")
    
    async def _validate_output(self, source_metadata: Dict[str, Any], output_metadata: Dict[str, Any], 
                            target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the output media against requirements.
        
        Args:
            source_metadata: Metadata of the source media
            output_metadata: Metadata of the output media
            target_format: Target format parameters
            
        Returns:
            Dictionary containing validation results
        """
        # Default validation structure
        validation = {
            "passed": True,
            "issues": []
        }
        
        # Validate basic format requirements
        try:
            # Check format type
            output_format = output_metadata.get("format", {}).get("format_name", "").lower()
            expected_format = target_format.get("format", "").lower()
            
            if expected_format and output_format != expected_format:
                validation["passed"] = False
                validation["issues"].append(f"Expected format {expected_format}, got {output_format}")
            
            # Check video codec if applicable
            has_video = any(stream.get("codec_type") == "video" for stream in output_metadata.get("streams", []))
            if has_video:
                video_stream = next((s for s in output_metadata.get("streams", []) if s.get("codec_type") == "video"), None)
                if video_stream:
                    output_codec = video_stream.get("codec_name", "").lower()
                    expected_codec = target_format.get("codec", "").lower()
                    
                    # Handle codec name variations
                    if expected_codec == "h264" and output_codec not in ["h264", "libx264"]:
                        validation["passed"] = False
                        validation["issues"].append(f"Expected video codec h264, got {output_codec}")
                    elif expected_codec == "h265" and output_codec not in ["h265", "hevc", "libx265"]:
                        validation["passed"] = False
                        validation["issues"].append(f"Expected video codec h265/hevc, got {output_codec}")
            
            # Check audio codec if applicable
            has_audio = any(stream.get("codec_type") == "audio" for stream in output_metadata.get("streams", []))
            if has_audio and "audio" in target_format["parameters"]:
                audio_stream = next((s for s in output_metadata.get("streams", []) if s.get("codec_type") == "audio"), None)
                if audio_stream:
                    output_codec = audio_stream.get("codec_name", "").lower()
                    expected_codec = target_format["parameters"]["audio"].get("codec", "").lower()
                    
                    if expected_codec and output_codec != expected_codec:
                        # Handle codec name variations
                        if not (expected_codec == "aac" and output_codec in ["aac", "aac_lc"]):
                            validation["passed"] = False
                            validation["issues"].append(f"Expected audio codec {expected_codec}, got {output_codec}")
            
            # Check for significant quality loss
            if has_video:
                source_video = next((s for s in source_metadata.get("streams", []) if s.get("codec_type") == "video"), None)
                output_video = next((s for s in output_metadata.get("streams", []) if s.get("codec_type") == "video"), None)
                
                if source_video and output_video:
                    # Check resolution change
                    source_width = int(source_video.get("width", 0))
                    source_height = int(source_video.get("height", 0))
                    output_width = int(output_video.get("width", 0))
                    output_height = int(output_video.get("height", 0))
                    
                    # Calculate resolution reduction percentage
                    if source_width > 0 and source_height > 0:
                        source_pixels = source_width * source_height
                        output_pixels = output_width * output_height
                        resolution_reduction = 100 - (output_pixels / source_pixels * 100)
                        
                        if resolution_reduction > 10:  # More than 10% reduction in pixels
                            validation["issues"].append(
                                f"Resolution reduced by {resolution_reduction:.1f}% "
                                f"({source_width}x{source_height} -> {output_width}x{output_height})"
                            )
            
            # Check if output file exists and has reasonable size
            source_size = int(source_metadata.get("format", {}).get("size", 0))
            output_size = int(output_metadata.get("format", {}).get("size", 0))
            
            if output_size <= 0:
                validation["passed"] = False
                validation["issues"].append("Output file has zero size")
            elif source_size > 0 and output_size < (source_size * 0.01):  # Output is less than 1% of source
                validation["issues"].append(f"Output file is suspiciously small ({output_size} bytes, {output_size/source_size:.1%} of source)")
            
            # Check duration change
            source_duration = float(source_metadata.get("format", {}).get("duration", 0))
            output_duration = float(output_metadata.get("format", {}).get("duration", 0))
            
            if source_duration > 0 and abs(output_duration - source_duration) > 1.0:  # More than 1 second difference
                duration_change_pct = abs(output_duration - source_duration) / source_duration * 100
                if duration_change_pct > 1:  # More than 1% change
                    validation["issues"].append(
                        f"Duration changed by {duration_change_pct:.1f}% "
                        f"({source_duration:.2f}s -> {output_duration:.2f}s)"
                    )
        
        except Exception as e:
            self.logger.error(f"Error during output validation: {e}")
            validation["passed"] = False
            validation["issues"].append(f"Validation error: {str(e)}")
        
        return validation
    
    def _parse_ffmpeg_output(self, stderr_output: str) -> List[str]:
        """Parse FFmpeg output to extract transformation information.
        
        Args:
            stderr_output: FFmpeg stderr output string
            
        Returns:
            List of transformation descriptions
        """
        transformations = []
        
        # Extract stream mapping information
        mapping_lines = [line for line in stderr_output.split('\n') if "Stream mapping:" in line or "->" in line]
        if mapping_lines:
            transformations.extend(mapping_lines)
        
        # Extract encoding parameters
        for line in stderr_output.split('\n'):
            if line.startswith("Output") or "encoder" in line or "bitrate" in line:
                transformations.append(line.strip())
        
        return transformations
    
    def _get_codec_info(self, metadata: Dict[str, Any]) -> str:
        """Extract codec information from media metadata.
        
        Args:
            metadata: Media metadata dictionary
            
        Returns:
            String describing the codec(s)
        """
        codecs = []
        
        for stream in metadata.get("streams", []):
            codec_type = stream.get("codec_type")
            codec_name = stream.get("codec_name")
            
            if codec_type and codec_name:
                codecs.append(f"{codec_type}:{codec_name}")
        
        return ", ".join(codecs) if codecs else "unknown"
    
    def _get_resolution(self, metadata: Dict[str, Any]) -> Dict[str, int]:
        """Extract resolution information from media metadata.
        
        Args:
            metadata: Media metadata dictionary
            
        Returns:
            Dictionary with width and height, or empty dict if not video
        """
        for stream in metadata.get("streams", []):
            if stream.get("codec_type") == "video":
                return {
                    "width": int(stream.get("width", 0)),
                    "height": int(stream.get("height", 0))
                }
        
        return {}
    
    def _calculate_quality_metrics(self, source_metadata: Dict[str, Any], output_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate basic quality metrics comparing source and output media.
        
        Args:
            source_metadata: Metadata of the source media
            output_metadata: Metadata of the output media
            
        Returns:
            Dictionary containing quality metrics
        """
        metrics = {}
        
        # Compare video streams if present
        source_video = next((s for s in source_metadata.get("streams", []) if s.get("codec_type") == "video"), None)
        output_video = next((s for s in output_metadata.get("streams", []) if s.get("codec_type") == "video"), None)
        
        if source_video and output_video:
            # Compare resolution
            source_pixels = int(source_video.get("width", 0)) * int(source_video.get("height", 0))
            output_pixels = int(output_video.get("width", 0)) * int(output_video.get("height", 0))
            
            if source_pixels > 0:
                resolution_ratio = output_pixels / source_pixels
                metrics["resolution_preservation"] = min(1.0, resolution_ratio) * 100
            
            # Compare bitrate if available
            source_bitrate = float(source_video.get("bit_rate", 0))
            output_bitrate = float(output_video.get("bit_rate", 0))
            
            if source_bitrate > 0 and output_bitrate > 0:
                bitrate_ratio = output_bitrate / source_bitrate
                metrics["bitrate_ratio"] = bitrate_ratio
            
            # Calculate estimated visual quality (simplified model)
            if "resolution_preservation" in metrics and "bitrate_ratio" in metrics:
                # Weighted combination of resolution and bitrate preservation
                resolution_weight = 0.6
                bitrate_weight = 0.4
                
                estimated_quality = (
                    resolution_weight * metrics["resolution_preservation"] + 
                    bitrate_weight * min(100, metrics["bitrate_ratio"] * 100)
                )
                
                metrics["estimated_visual_quality"] = min(100, estimated_quality)
        
        # Compare audio streams if present
        source_audio = next((s for s in source_metadata.get("streams", []) if s.get("codec_type") == "audio"), None)
        output_audio = next((s for s in output_metadata.get("streams", []) if s.get("codec_type") == "audio"), None)
        
        if source_audio and output_audio:
            # Compare audio bitrate
            source_bitrate = float(source_audio.get("bit_rate", 0))
            output_bitrate = float(output_audio.get("bit_rate", 0))
            
            if source_bitrate > 0 and output_bitrate > 0:
                bitrate_ratio = output_bitrate / source_bitrate
                metrics["audio_bitrate_ratio"] = bitrate_ratio
                metrics["estimated_audio_quality"] = min(100, bitrate_ratio * 100)
        
        return metrics
    
    def _calculate_compression_ratio(self, source_path: str, output_path: str) -> float:
        """Calculate compression ratio between source and output files.
        
        Args:
            source_path: Path to the source file
            output_path: Path to the output file
            
        Returns:
            Compression ratio (source_size / output_size)
        """
        if not os.path.exists(source_path) or not os.path.exists(output_path):
            return 0.0
        
        source_size = os.path.getsize(source_path)
        output_size = os.path.getsize(output_path)
        
        if output_size <= 0:
            return 0.0
        
        return source_size / output_size
    
    def _get_default_codec(self, format_type: str) -> str:
        """Get the default codec for a given format type.
        
        Args:
            format_type: Media format type string
            
        Returns:
            Default codec name for the format
        """
        format_codec_map = {
            "mp4": "h264",
            "mov": "prores",
            "mkv": "h265",
            "webm": "vp9",
            "avi": "h264",
            "mxf": "dnxhd",
            "mp3": "mp3",
            "wav": "pcm_s16le",
            "aac": "aac",
            "flac": "flac",
            "ogg": "vorbis",
            "m4a": "aac",
            "jpg": "mjpeg",
            "png": "png",
            "tiff": "tiff",
            "webp": "webp",
            "avif": "libaom-av1"
        }
        
        return format_codec_map.get(format_type.lower(), "h264")