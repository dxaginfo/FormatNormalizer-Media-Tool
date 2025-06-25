import google.generativeai as genai
import os
import json
from typing import Dict, Any, List, Optional

class GeminiMediaAnalyzer:
    """Media analysis module using Google's Gemini API for content-aware encoding decisions."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini Media Analyzer.
        
        Args:
            api_key: Gemini API key. If None, tries to get from GEMINI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key must be provided or set as GEMINI_API_KEY environment variable")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    async def analyze_media_content(self, media_metadata: Dict[str, Any], target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze media content and recommend optimal encoding parameters.
        
        Args:
            media_metadata: Technical metadata about the source media
            target_format: Target format information
            
        Returns:
            Dict containing recommended encoding parameters
        """
        # Prepare the prompt for Gemini API
        prompt = self._build_analysis_prompt(media_metadata, target_format)
        
        # Get recommendations from Gemini
        response = await self.model.generate_content_async(prompt)
        
        # Extract and parse recommendations
        try:
            recommendations = self._parse_recommendations(response.text)
            return recommendations
        except Exception as e:
            print(f"Error parsing Gemini recommendations: {e}")
            # Return basic fallback recommendations if parsing fails
            return self._get_fallback_recommendations(target_format)
    
    def _build_analysis_prompt(self, media_metadata: Dict[str, Any], target_format: Dict[str, Any]) -> str:
        """Build a prompt for Gemini to analyze media and recommend encoding parameters."""
        return f"""You are an expert media encoding specialist. Analyze the following media metadata and recommend 
        optimal encoding parameters for the specified target format.
        
        Source Media Metadata:
        ```json
        {json.dumps(media_metadata, indent=2)}
        ```
        
        Target Format Requirements:
        ```json
        {json.dumps(target_format, indent=2)}
        ```
        
        Based on the content characteristics and target format, provide recommendations for:
        1. Optimal codec parameters
        2. Bitrate strategy (VBR/CBR/CRF) with specific values
        3. Other FFmpeg parameters to optimize quality and file size
        4. Any content-specific optimizations
        
        Return your recommendations as a valid JSON object with the following structure:
        ```json
        {{
          "codec_parameters": {{}},
          "bitrate_strategy": {{}},
          "ffmpeg_options": [],
          "optimizations": {{}}
        }}
        ```
        
        Provide only the JSON response without any additional text.
        """
    
    def _parse_recommendations(self, response_text: str) -> Dict[str, Any]:
        """Parse the recommendations from Gemini's response."""
        # Extract JSON from response text - sometimes Gemini includes explanatory text
        try:
            # Try to find JSON block in the response if it's not a pure JSON response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx+1]
                return json.loads(json_str)
            else:
                # If no JSON found, try to parse the whole response
                return json.loads(response_text)
        except json.JSONDecodeError:
            raise ValueError(f"Could not parse valid JSON from Gemini response: {response_text}")
    
    def _get_fallback_recommendations(self, target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback encoding recommendations based on target format."""
        format_type = target_format.get('format', '').lower()
        codec = target_format.get('codec', '').lower()
        
        # Default recommendations
        recommendations = {
            "codec_parameters": {},
            "bitrate_strategy": {"type": "VBR", "value": "medium"},
            "ffmpeg_options": [],
            "optimizations": {}
        }
        
        # Video-specific recommendations
        if format_type in ['mp4', 'mov', 'mkv']:
            if codec == 'h264':
                recommendations["codec_parameters"] = {"preset": "medium", "profile": "high"}
                recommendations["bitrate_strategy"] = {"type": "CRF", "value": 23}
                recommendations["ffmpeg_options"] = ["-movflags", "+faststart"]
            elif codec == 'h265' or codec == 'hevc':
                recommendations["codec_parameters"] = {"preset": "medium", "profile": "main"}
                recommendations["bitrate_strategy"] = {"type": "CRF", "value": 28}
            elif codec == 'prores':
                recommendations["codec_parameters"] = {"profile": "standard"}
                recommendations["bitrate_strategy"] = {"type": "CBR", "value": "45000k"}
            elif codec == 'av1':
                recommendations["codec_parameters"] = {"preset": "medium", "tile-columns": 2, "row-mt": 1}
                recommendations["bitrate_strategy"] = {"type": "CRF", "value": 30}
        
        # Audio-specific recommendations
        elif format_type in ['wav', 'mp3', 'aac', 'flac']:
            if codec == 'aac':
                recommendations["codec_parameters"] = {"profile": "aac_low"}
                recommendations["bitrate_strategy"] = {"type": "CBR", "value": "192k"}
            elif codec == 'mp3':
                recommendations["bitrate_strategy"] = {"type": "CBR", "value": "320k"}
            elif codec == 'flac':
                recommendations["codec_parameters"] = {"compression_level": 8}
        
        return recommendations

class AIAnalysisModule:
    """Module that integrates various AI analysis capabilities for media processing."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.gemini_analyzer = GeminiMediaAnalyzer(api_key)
    
    async def analyze_content(self, media_path: str, media_metadata: Dict[str, Any], 
                            target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze media content and provide encoding recommendations.
        
        Args:
            media_path: Path to the media file
            media_metadata: Technical metadata about the media
            target_format: Target format information
            
        Returns:
            Dict containing AI analysis results and recommendations
        """
        # Get encoding recommendations from Gemini
        encoding_recommendations = await self.gemini_analyzer.analyze_media_content(
            media_metadata, target_format
        )
        
        # Combine all analysis results
        analysis_results = {
            "encoding_recommendations": encoding_recommendations,
            "content_type": self._infer_content_type(media_metadata),
            "quality_preservation": self._calculate_quality_preservation(media_metadata, target_format),
            "optimizations": encoding_recommendations.get("optimizations", {})
        }
        
        return analysis_results
    
    def _infer_content_type(self, media_metadata: Dict[str, Any]) -> str:
        """Infer the type of content based on metadata."""
        # Simple inference based on metadata
        if "video" in media_metadata:
            frame_rate = media_metadata.get("video", {}).get("frame_rate", 0)
            if frame_rate < 24:
                return "animation"
            elif frame_rate >= 48:
                return "action"
            else:
                return "general"
        elif "audio" in media_metadata:
            channels = media_metadata.get("audio", {}).get("channels", 0)
            if channels > 2:
                return "surround"
            else:
                return "stereo"
        else:
            return "unknown"
    
    def _calculate_quality_preservation(self, media_metadata: Dict[str, Any], 
                                      target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate expected quality preservation metrics."""
        # Simple quality preservation estimation
        quality_metrics = {}
        
        # Video quality estimation
        if "video" in media_metadata:
            source_codec = media_metadata.get("video", {}).get("codec", "")
            target_codec = target_format.get("codec", "")
            
            # Estimate quality preservation percentage
            if source_codec == target_codec:
                quality_metrics["video_quality"] = 100
            elif source_codec in ["prores", "dnxhd"] and target_codec in ["h264", "h265"]:
                quality_metrics["video_quality"] = 85
            elif source_codec in ["h264"] and target_codec in ["h265", "av1"]:
                quality_metrics["video_quality"] = 95
            else:
                quality_metrics["video_quality"] = 80
        
        # Audio quality estimation
        if "audio" in media_metadata:
            source_codec = media_metadata.get("audio", {}).get("codec", "")
            source_sample_rate = media_metadata.get("audio", {}).get("sample_rate", 0)
            target_codec = target_format.get("audio_codec", "")
            
            if source_codec == target_codec:
                quality_metrics["audio_quality"] = 100
            elif source_codec in ["pcm", "wav"] and target_codec in ["aac", "mp3"]:
                quality_metrics["audio_quality"] = 85
            else:
                quality_metrics["audio_quality"] = 90
                
        return quality_metrics