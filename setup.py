from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="format_normalizer",
    version="1.0.0",
    author="dxaginfo",
    author_email="support@dxaginfo-media-tools.com",
    description="Media format normalization and conversion tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dxaginfo/FormatNormalizer-Media-Tool",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.21.0",
        "python-multipart>=0.0.6",
        "pydantic>=2.0.0",
        "pyyaml>=6.0.0",
        "asyncio>=3.4.3",
        "aiohttp>=3.8.4",
        "requests>=2.28.2",
        "google-cloud-storage>=2.7.0",
        "google-cloud-firestore>=2.9.1",
        "google-generativeai>=0.3.0"
    ],
    entry_points={
        "console_scripts": [
            "format-normalizer=format_normalizer.cli:main",
        ],
    },
)