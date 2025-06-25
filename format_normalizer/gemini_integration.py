import os
import json
import google.generativeai as genai
from typing import Dict, Any, List, Optional, Tuple

class GeminiFormatAnalyzer:
    """Integrates Gemini AI for media format analysis and optimization."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini Format Analyzer.
        
        Args:
            api_key: Gemini API key. If None, tries to get from GEMINI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key must be provided or set as GEMINI_API_KEY environment variable")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    async def analyze_format_compatibility(self, source_format: Dict[str, Any], target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze compatibility between source and target formats.
        
        Args:
            source_format: Details of the source media format
            target_format: Details of the target media format
            
        Returns:
            Dict containing compatibility analysis and recommendations
        """
        # Build prompt for format compatibility analysis
        prompt = self._build_compatibility_prompt(source_format, target_format)
        
        # Get analysis from Gemini
        response = await self.model.generate_content_async(prompt)
        
        # Parse the analysis
        try:
            compatibility_analysis = self._parse_analysis(response.text)
            return compatibility_analysis
        except Exception as e:
            print(f"Error parsing Gemini format compatibility analysis: {e}")
            return self._get_fallback_compatibility_analysis(source_format, target_format)
    
    async def recommend_conversion_parameters(self, media_metadata: Dict[str, Any], target_format: Dict[str, Any], content_type: str) -> Dict[str, Any]:
        """Recommend optimal conversion parameters for specific content type.
        
        Args:
            media_metadata: Technical metadata about the source media
            target_format: Target format requirements
            content_type: Type of content (e.g., film, animation, sports)
            
        Returns:
            Dict containing recommended conversion parameters
        """
        # Build prompt for parameter recommendations
        prompt = self._build_parameters_prompt(media_metadata, target_format, content_type)
        
        # Get recommendations from Gemini
        response = await self.model.generate_content_async(prompt)
        
        # Parse the recommendations
        try:
            conversion_parameters = self._parse_analysis(response.text)
            return conversion_parameters
        except Exception as e:
            print(f"Error parsing Gemini conversion parameter recommendations: {e}")
            return self._get_fallback_conversion_parameters(media_metadata, target_format)
    
    async def validate_output_quality(self, source_metadata: Dict[str, Any], output_metadata: Dict[str, Any], 
                                    target_requirements: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Validate the quality of the output media against requirements.
        
        Args:
            source_metadata: Technical metadata about the source media
            output_metadata: Technical metadata about the output media
            target_requirements: Target quality requirements
            
        Returns:
            Tuple of (passed: bool, validation_results: Dict)
        """
        # Build prompt for quality validation
        prompt = self._build_validation_prompt(source_metadata, output_metadata, target_requirements)
        
        # Get validation from Gemini
        response = await self.model.generate_content_async(prompt)
        
        # Parse the validation results
        try:
            validation_results = self._parse_analysis(response.text)
            passed = validation_results.get('passed', False)
            return (passed, validation_results)
        except Exception as e:
            print(f"Error parsing Gemini output quality validation: {e}")
            return (False, {"passed": False, "error": str(e), "issues": ["Failed to parse validation results"]})
    
    def _build_compatibility_prompt(self, source_format: Dict[str, Any], target_format: Dict[str, Any]) -> str:
        """Build a prompt for format compatibility analysis."""
        return f"""You are an expert in media format conversion and compatibility. Analyze the compatibility 
        between the following source and target formats and provide detailed recommendations for conversion.
        
        Source Format:
        ```json
        {json.dumps(source_format, indent=2)}
        ```
        
        Target Format:
        ```json
        {json.dumps(target_format, indent=2)}
        ```
        
        Provide a detailed analysis of:
        1. Compatibility issues between the formats
        2. Quality impact of the conversion
        3. Recommended conversion approach
        4. Any special considerations for this specific conversion
        
        Return your analysis as a valid JSON object with the following structure:
        ```json
        {{
          "compatibility_score": 0-100,
          "issues": [],
          "quality_impact": {{}},
          "recommended_approach": {{}},
          "special_considerations": []
        }}
        ```
        
        Provide only the JSON response without any additional text.
        """
    
    def _build_parameters_prompt(self, media_metadata: Dict[str, Any], target_format: Dict[str, Any], content_type: str) -> str:
        """Build a prompt for conversion parameter recommendations."""
        return f"""You are an expert in media encoding and optimization. Recommend optimal conversion parameters 
        for the following media based on its content type and target format requirements.
        
        Media Metadata:
        ```json
        {json.dumps(media_metadata, indent=2)}
        ```
        
        Target Format:
        ```json
        {json.dumps(target_format, indent=2)}
        ```
        
        Content Type: {content_type}
        
        Based on the content type and technical requirements, recommend:
        1. Optimal codec-specific parameters
        2. Appropriate bitrate strategy and values
        3. Quality preservation techniques
        4. Content-specific optimizations
        5. FFmpeg command parameters
        
        Return your recommendations as a valid JSON object with the following structure:
        ```json
        {{
          "codec_parameters": {{}},
          "bitrate_strategy": {{}},
          "quality_preservation": {{}},
          "content_optimizations": {{}},
          "ffmpeg_parameters": []
        }}
        ```
        
        Provide only the JSON response without any additional text.
        """
    
    def _build_validation_prompt(self, source_metadata: Dict[str, Any], output_metadata: Dict[str, Any], 
                               target_requirements: Dict[str, Any]) -> str:
        """Build a prompt for output quality validation."""
        return f"""You are an expert in media quality assessment. Validate the quality of the converted media 
        against the target requirements.
        
        Source Media Metadata:
        ```json
        {json.dumps(source_metadata, indent=2)}
        ```
        
        Output Media Metadata:
        ```json
        {json.dumps(output_metadata, indent=2)}
        ```
        
        Target Requirements:
        ```json
        {json.dumps(target_requirements, indent=2)}
        ```
        
        Perform a detailed quality assessment:
        1. Determine if the output meets all technical requirements
        2. Identify any quality issues or losses
        3. Evaluate the success of the conversion
        4. Suggest improvements if needed
        
        Return your validation as a valid JSON object with the following structure:
        ```json
        {{
          "passed": true/false,
          "technical_compliance": {{}},
          "quality_assessment": {{}},
          "issues": [],
          "improvements": []
        }}
        ```
        
        Provide only the JSON response without any additional text.
        """
    
    def _parse_analysis(self, response_text: str) -> Dict[str, Any]:
        """Parse the analysis from Gemini's response."""
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
    
    def _get_fallback_compatibility_analysis(self, source_format: Dict[str, Any], target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback compatibility analysis if Gemini analysis fails."""
        # Extract basic format information
        source_format_type = source_format.get('format', '').lower()
        target_format_type = target_format.get('format', '').lower()
        source_codec = source_format.get('codec', '').lower()
        target_codec = target_format.get('codec', '').lower()
        
        # Default compatibility score
        compatibility_score = 80
        issues = []
        
        # Check basic compatibility
        if source_format_type != target_format_type:
            compatibility_score -= 20
            issues.append(f"Format type change from {source_format_type} to {target_format_type}")
        
        if source_codec != target_codec:
            compatibility_score -= 10
            issues.append(f"Codec change from {source_codec} to {target_codec}")
        
        # Basic quality impact assessment
        quality_impact = {
            "visual_quality": "high" if compatibility_score > 70 else "medium",
            "audio_quality": "high" if compatibility_score > 70 else "medium",
            "estimated_loss": f"{100 - compatibility_score}%"
        }
        
        # Basic recommended approach
        recommended_approach = {
            "method": "direct_conversion" if compatibility_score > 60 else "two_step_conversion",
            "tools": ["FFmpeg"],
            "priority": "quality" if target_format.get('preset') == 'high' else "balance"
        }
        
        return {
            "compatibility_score": compatibility_score,
            "issues": issues,
            "quality_impact": quality_impact,
            "recommended_approach": recommended_approach,
            "special_considerations": []
        }
    
    def _get_fallback_conversion_parameters(self, media_metadata: Dict[str, Any], target_format: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback conversion parameters if Gemini recommendations fail."""
        # Extract basic format information
        format_type = target_format.get('format', '').lower()
        codec = target_format.get('codec', '').lower()
        preset = target_format.get('preset', 'medium').lower()
        
        # Default codec parameters
        codec_parameters = {}
        bitrate_strategy = {}
        ffmpeg_parameters = []
        
        # Set parameters based on format and codec
        if format_type in ['mp4', 'mov', 'mkv'] and codec in ['h264', 'libx264']:
            codec_parameters = {
                "preset": preset,
                "profile": "high",
                "level": "4.1",
                "pixel_format": "yuv420p"
            }
            
            if preset == 'high':
                bitrate_strategy = {"type": "CRF", "value": 18}
            elif preset == 'low':
                bitrate_strategy = {"type": "CRF", "value": 28}
            else:  # medium
                bitrate_strategy = {"type": "CRF", "value": 23}
                
            ffmpeg_parameters = ["-movflags", "+faststart"]
            
        elif format_type in ['mp4', 'mov', 'mkv'] and codec in ['h265', 'hevc', 'libx265']:
            codec_parameters = {
                "preset": preset,
                "profile": "main",
                "pixel_format": "yuv420p"
            }
            
            if preset == 'high':
                bitrate_strategy = {"type": "CRF", "value": 22}
            elif preset == 'low':
                bitrate_strategy = {"type": "CRF", "value": 32}
            else:  # medium
                bitrate_strategy = {"type": "CRF", "value": 28}
        
        elif format_type in ['mp4', 'mov'] and codec in ['prores', 'prores_ks']:
            codec_parameters = {
                "profile": "3" if preset == 'high' else "2",  # 3=HQ, 2=Standard
                "vendor": "apl0"
            }
            
            bitrate_strategy = {"type": "CBR", "value": "45000k" if preset == 'high' else "30000k"}
        
        # Basic audio parameters for audio-only or audio track in video
        audio_parameters = {}
        if 'audio' in media_metadata:
            audio_codec = target_format.get('audio_codec', 'aac').lower()
            
            if audio_codec == 'aac':
                audio_parameters = {
                    "codec": "aac",
                    "bitrate": "192k" if preset == 'high' else "128k"
                }
            elif audio_codec == 'mp3':
                audio_parameters = {
                    "codec": "libmp3lame",
                    "bitrate": "320k" if preset == 'high' else "192k"
                }
        
        return {
            "codec_parameters": codec_parameters,
            "audio_parameters": audio_parameters,
            "bitrate_strategy": bitrate_strategy,
            "quality_preservation": {"priority": preset},
            "content_optimizations": {},
            "ffmpeg_parameters": ffmpeg_parameters
        }