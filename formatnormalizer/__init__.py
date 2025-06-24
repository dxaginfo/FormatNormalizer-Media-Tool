"""
FormatNormalizer: Media Format Normalization Tool

A comprehensive media format conversion and standardization tool
that uses FFmpeg, Google Cloud, and Gemini API.
"""

__version__ = "0.1.0"

from .normalizer import FormatNormalizer
from .models import NormalizationResult, BatchJob