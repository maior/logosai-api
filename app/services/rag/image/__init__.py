"""Image processing module for RAG system."""

from app.services.rag.image.processor import ImageProcessor
from app.services.rag.image.extractor import (
    extract_images_from_pdf,
    extract_caption,
    encode_image_base64,
)

__all__ = [
    "ImageProcessor",
    "extract_images_from_pdf",
    "extract_caption",
    "encode_image_base64",
]
