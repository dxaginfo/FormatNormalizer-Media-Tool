#!/usr/bin/env python3

import os
import sys
import json
import argparse
import asyncio
import logging
from typing import Dict, Any, Optional

from .normalizer import FormatNormalizer
from .__init__ import __version__

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def normalize_media(args: argparse.Namespace) -> None:
    """Normalize media files based on command-line arguments."""
    # Initialize normalizer
    normalizer = FormatNormalizer(ai_api_key=args.api_key, temp_dir=args.temp_dir)
    
    # Process target format
    target_format = {
        "format": args.format,
        "codec": args.codec
    }
    
    # Add custom parameters if provided
    if args.parameters:
        try:
            custom_params = json.loads(args.parameters)
            target_format["parameters"] = custom_params
        except json.JSONDecodeError:
            logger.error("Invalid JSON format for parameters")
            sys.exit(1)
    
    # Ensure output directory exists
    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Run normalization
        result = await normalizer.normalize(
            source_path=args.input,
            output_path=args.output,
            target_format=target_format,
            preset=args.preset,
            enable_ai=args.ai,
            validate_output=args.validate
        )
        
        # Print results
        if args.verbose:
            print(json.dumps(result, indent=2))
        else:
            print(f"\nNormalization completed successfully")
            print(f"Output file: {result['result']['uri']}")
            print(f"Format: {result['result']['format']}, Codec: {result['result']['codec']}")
            print(f"File size: {result['result']['fileSize'] / (1024 * 1024):.2f} MB")
            print(f"Processing time: {result['performance']['processingTime']:.2f} seconds")
            
            if 'validation' in result:
                if result['validation']['passed']:
                    print("Validation: Passed ✓")
                else:
                    print("Validation: Failed ✗")
                    for issue in result['validation']['issues']:
                        print(f"  - {issue}")
            
        # Save detailed results if requested
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(result, f, indent=2)
                logger.info(f"Detailed results saved to {args.output_json}")
        
    except Exception as e:
        logger.error(f"Normalization failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the command-line interface."""
    parser = argparse.ArgumentParser(description="FormatNormalizer - Media format normalization tool")
    parser.add_argument('-v', '--version', action='version', version=f'FormatNormalizer {__version__}')
    
    # Input and output options
    parser.add_argument('-i', '--input', required=True, help='Input media file path')
    parser.add_argument('-o', '--output', required=True, help='Output media file path')
    
    # Format options
    parser.add_argument('-f', '--format', default='mp4', help='Target format (e.g., mp4, mov, webm)')
    parser.add_argument('-c', '--codec', help='Target codec (e.g., h264, h265, prores)')
    parser.add_argument('-p', '--preset', default='standard',
                        choices=['web', 'social', 'standard', 'broadcast', 'archive', 'mobile'],
                        help='Quality preset')
    parser.add_argument('--parameters', help='Additional parameters as JSON string')
    
    # Processing options
    parser.add_argument('--ai', action='store_true', help='Enable AI-powered optimization')
    parser.add_argument('--api-key', help='Gemini API key for AI features')
    parser.add_argument('--validate', action='store_true', default=True, help='Validate output file')
    parser.add_argument('--temp-dir', help='Directory for temporary files')
    
    # Output options
    parser.add_argument('--verbose', action='store_true', help='Print detailed output')
    parser.add_argument('--output-json', help='Save detailed results to JSON file')
    
    args = parser.parse_args()
    
    # Check that input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Auto-determine codec if not specified
    if not args.codec:
        codec_map = {
            'mp4': 'h264',
            'mov': 'prores',
            'webm': 'vp9',
            'mkv': 'h265',
            'mp3': 'mp3',
            'wav': 'pcm_s16le'
        }
        args.codec = codec_map.get(args.format, 'h264')
        logger.info(f"Auto-selected codec: {args.codec} for format: {args.format}")
    
    # Check for Gemini API key if AI is enabled
    if args.ai and not args.api_key:
        args.api_key = os.environ.get('GEMINI_API_KEY')
        if not args.api_key:
            print("Error: Gemini API key is required for AI features.")
            print("Provide it with --api-key or set the GEMINI_API_KEY environment variable.")
            sys.exit(1)
    
    # Run the async normalization function
    asyncio.run(normalize_media(args))


if __name__ == "__main__":
    main()