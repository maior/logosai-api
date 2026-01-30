"""PDF image extraction utilities."""

import io
import re
import base64
import logging
from datetime import datetime
from typing import Any, Optional

from PIL import Image

logger = logging.getLogger(__name__)


def extract_images_from_pdf(
    pdf_path: str,
    user_email: str,
    file_name: str,
    project_id: str,
    min_image_size: int = 5000,
) -> list[dict[str, Any]]:
    """
    Extract images and captions from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        user_email: User email for metadata
        file_name: Original file name
        project_id: Project ID
        min_image_size: Minimum image data size in bytes

    Returns:
        List of image documents with metadata
    """
    try:
        import PyPDF2

        images_with_captions = []

        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)

            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]

                if "/XObject" not in page["/Resources"]:
                    continue

                x_object = page["/Resources"]["/XObject"].get_object()

                for idx, obj in enumerate(x_object):
                    if x_object[obj]["/Subtype"] != "/Image":
                        continue

                    size = (x_object[obj]["/Width"], x_object[obj]["/Height"])
                    data = x_object[obj].get_data()

                    # Skip small images
                    if len(data) <= min_image_size:
                        continue

                    # Process image data
                    img = _process_image_data(data, size, x_object[obj], idx, page_num)

                    if img is None:
                        continue

                    # Extract caption
                    caption = extract_caption(page)

                    # Encode image
                    img_str = encode_image_base64(img)

                    # Create document
                    img_doc = _create_image_document(
                        user_email=user_email,
                        file_name=file_name,
                        project_id=project_id,
                        page_num=page_num,
                        image_index=idx,
                        image_data=img_str,
                        caption=caption,
                    )
                    images_with_captions.append(img_doc)

        logger.info(f"Extracted {len(images_with_captions)} images from {pdf_path}")
        return images_with_captions

    except Exception as e:
        logger.error(f"Error extracting images from PDF: {e}")
        return []


def extract_images_with_fitz(
    pdf_path: str,
    user_email: str,
    file_name: str,
    project_id: str,
    min_image_size: int = 1000,
) -> list[dict[str, Any]]:
    """
    Extract images using PyMuPDF (fitz) - better quality extraction.

    Args:
        pdf_path: Path to the PDF file
        user_email: User email for metadata
        file_name: Original file name
        project_id: Project ID
        min_image_size: Minimum image data size in bytes

    Returns:
        List of image documents with metadata
    """
    try:
        import fitz  # PyMuPDF

        images_with_captions = []
        pdf_file = fitz.open(pdf_path)

        for page_num, page in enumerate(pdf_file):
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = pdf_file.extract_image(xref)
                image_bytes = base_image["image"]

                # Skip small images
                if len(image_bytes) <= min_image_size:
                    continue

                try:
                    pil_img = Image.open(io.BytesIO(image_bytes))
                except Exception as e:
                    logger.warning(
                        f"Failed to open image on page {page_num + 1}, "
                        f"image {img_index + 1}: {e}"
                    )
                    continue

                # Extract caption
                caption = _extract_caption_fitz(page)

                # Encode image
                img_str = encode_image_base64(pil_img)

                # Create document
                img_doc = _create_image_document(
                    user_email=user_email,
                    file_name=file_name,
                    project_id=project_id,
                    page_num=page_num,
                    image_index=img_index,
                    image_data=img_str,
                    caption=caption,
                )
                images_with_captions.append(img_doc)

        pdf_file.close()
        logger.info(f"Extracted {len(images_with_captions)} images from {pdf_path}")
        return images_with_captions

    except ImportError:
        logger.warning("PyMuPDF not installed, falling back to PyPDF2")
        return extract_images_from_pdf(
            pdf_path, user_email, file_name, project_id, min_image_size
        )
    except Exception as e:
        logger.error(f"Error extracting images with fitz: {e}")
        return []


def extract_caption(page: Any) -> str:
    """
    Extract caption from a PDF page.

    Args:
        page: PyPDF2 page object

    Returns:
        Extracted caption or default message
    """
    try:
        text = page.extract_text()
        # Look for figure captions
        pattern = r"(Fig(?:ure)?\.?\s*\d+[.:]\s*[^\n]+(?:\n[^\n]+)*)"
        potential_captions = re.findall(pattern, text, re.MULTILINE)
        return potential_captions[0] if potential_captions else "No caption found"
    except Exception as e:
        logger.error(f"Caption extraction error: {e}")
        return "No caption found"


def _extract_caption_fitz(page: Any) -> str:
    """
    Extract caption from a fitz page.

    Args:
        page: PyMuPDF page object

    Returns:
        Extracted caption or default message
    """
    try:
        text = page.get_text()
        # Multi-line caption pattern
        pattern = r"(Fig(?:ure)?\.?\s*\d+[.:]\s*[^\n]+(?:\n(?!Fig(?:ure)?\.?\s*\d+)[^\n]+)*)"
        potential_captions = re.findall(pattern, text)

        if potential_captions:
            # Select longest caption
            longest_caption = max(potential_captions, key=len)
            return " ".join(longest_caption.split())
        else:
            return "No caption found"
    except Exception as e:
        logger.error(f"Fitz caption extraction error: {e}")
        return "No caption found"


def encode_image_base64(img: Image.Image, format: str = "PNG") -> str:
    """
    Encode a PIL Image to base64.

    Args:
        img: PIL Image object
        format: Output format

    Returns:
        Base64 encoded string
    """
    try:
        buffered = io.BytesIO()
        img.save(buffered, format=format)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"Image encoding error: {e}")
        return ""


def resize_image(
    image_data: str,
    scale: float = 0.75,
) -> str:
    """
    Resize an image by scale factor.

    Args:
        image_data: Base64 encoded image data
        scale: Scale factor (0-1)

    Returns:
        Base64 encoded resized image
    """
    try:
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        width, height = image.size
        new_size = (int(width * scale), int(height * scale))
        resized_image = image.resize(new_size, Image.LANCZOS)

        buffered = io.BytesIO()
        resized_image.save(buffered, format=image.format or "PNG")

        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        logger.error(f"Image resize error: {e}")
        return image_data


def _process_image_data(
    data: bytes,
    size: tuple[int, int],
    x_object: Any,
    idx: int,
    page_num: int,
) -> Optional[Image.Image]:
    """Process image data from PDF XObject."""
    try:
        # Validate data
        if not data or len(data) < 100:
            return None

        # Validate size
        if size[0] <= 0 or size[1] <= 0:
            return None

        # Try direct open
        try:
            return Image.open(io.BytesIO(data))
        except Exception:
            pass

        # Process based on filter type
        if "/Filter" in x_object:
            filter_type = x_object["/Filter"]
            if isinstance(filter_type, list):
                filter_type = filter_type[0]

            try:
                if filter_type == "/DCTDecode":  # JPEG
                    return Image.open(io.BytesIO(data))
                elif filter_type == "/FlateDecode":  # PNG
                    try:
                        return Image.frombytes("RGB", size, data)
                    except Exception:
                        return Image.frombytes("L", size, data)
                elif filter_type == "/JPXDecode":  # JPEG2000
                    return Image.open(io.BytesIO(data))
                else:
                    return Image.frombytes("RGB", size, data)
            except Exception:
                # Try different modes
                for mode in ["RGB", "RGBA", "L"]:
                    try:
                        img = Image.frombytes(mode, size, data)
                        if img and img.size[0] > 0 and img.size[1] > 0:
                            return img
                    except Exception:
                        continue
        else:
            try:
                return Image.frombytes("RGB", size, data)
            except Exception:
                pass

        return None

    except Exception as e:
        logger.error(f"Failed to process image {idx} on page {page_num + 1}: {e}")
        return None


def _create_image_document(
    user_email: str,
    file_name: str,
    project_id: str,
    page_num: int,
    image_index: int,
    image_data: str,
    caption: str,
    embedding: Optional[list[float]] = None,
) -> dict[str, Any]:
    """Create an image document for indexing."""
    image_id = f"page{page_num + 1}_img{image_index + 1}"

    return {
        "image_id": image_id,
        "image_data": image_data,
        "caption": caption,
        "page_num": page_num + 1,
        "vector": embedding or [],
        "file_name": file_name,
        "timestamp": datetime.now().isoformat(),
        "project_id": project_id,
        "user_email": user_email,
    }
