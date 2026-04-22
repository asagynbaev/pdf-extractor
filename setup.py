#!/usr/bin/env python3
"""Setup script for pdf-explainer package"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="pdf-explainer",
    version="1.0.0",
    author="PDF Extractor Contributors",
    description="Production-grade batch PDF extraction pipeline for LLM fine-tuning datasets. Extract text, tables, images, and links from hundreds of PDFs with zero data loss, automatic quality control, and ready-to-use training data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/pdf-explainer",
    project_urls={
        "Documentation": "https://github.com/yourusername/pdf-explainer/blob/main/README.md",
        "Bug Tracker": "https://github.com/yourusername/pdf-explainer/issues",
        "Source Code": "https://github.com/yourusername/pdf-explainer",
    },
    packages=find_packages(),
    py_modules=["batch_extract"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Natural Language :: Russian",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business",
        "Topic :: Text Processing",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords=[
        "pdf",
        "extraction",
        "ocr",
        "paddleocr",
        "nlp",
        "natural language processing",
        "fine-tuning",
        "llm",
        "large language model",
        "dataset",
        "batch processing",
        "production",
        "zero data loss",
        "quality control",
        "machine learning",
        "deep learning",
        "text extraction",
        "document processing",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "gpu": [
            "paddlepaddle-gpu==3.2.0",
        ],
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=22.0",
            "flake8>=5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pdf-extract=batch_extract:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
