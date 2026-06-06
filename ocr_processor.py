"""
OCR processing module for text extraction and bounding box detection
"""
import os
import logging
from typing import List, Tuple, Dict, Any
from pathlib import Path
import io

try:
    from PIL import Image
    import pytesseract
except ImportError:
    pass

try:
    from paddleocr import PaddleOCR
except ImportError:
    pass

from pdf2image import convert_from_path
from config import OCR_ENGINE, TESSERACT_CMD

logger = logging.getLogger(__name__)

# Initialize OCR engines
_tesseract_available = False
_paddleocr_available = False
_paddle_ocr = None

try:
    import pytesseract

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    # Verify installation
    pytesseract.get_tesseract_version()

    _tesseract_available = True
    logger.info("Tesseract OCR initialized successfully")

except Exception as e:
    _tesseract_available = False
    logger.warning(f"Tesseract not available: {e}")

print("Tesseract Available =", _tesseract_available)
print("Tesseract Path =", TESSERACT_CMD)


class OCRProcessor:
    """OCR processor for extracting text and bounding boxes from images"""

    @staticmethod
    def convert_pdf_to_images(pdf_path: str) -> List[Image.Image]:
        """
        Convert PDF to list of PIL Image objects
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of PIL Image objects (one per page)
        """
        try:
            images = convert_from_path(pdf_path, fmt="png")
            logger.info(f"Converted PDF {pdf_path} to {len(images)} images")
            return images
        except Exception as e:
            logger.error(f"Error converting PDF {pdf_path}: {e}")
            raise

    @staticmethod
    def load_tiff(tiff_path: str) -> List[Image.Image]:
        """
        Load TIFF file which may have multiple pages
        
        Args:
            tiff_path: Path to TIFF file
            
        Returns:
            List of PIL Image objects (one per page)
        """
        try:
            images = []
            img = Image.open(tiff_path)
            
            # Check if multi-page TIFF
            try:
                for i in range(img.n_frames):
                    img.seek(i)
                    images.append(img.convert('RGB'))
            except (AttributeError, EOFError):
                # Single page TIFF
                images.append(img.convert('RGB'))
            
            logger.info(f"Loaded TIFF {tiff_path} with {len(images)} pages")
            return images
        except Exception as e:
            logger.error(f"Error loading TIFF {tiff_path}: {e}")
            raise

    @staticmethod
    def load_file(file_path: str) -> Tuple[List[Image.Image], int]:
        """
        Load file and convert to images
        
        Args:
            file_path: Path to PDF or TIFF file
            
        Returns:
            Tuple of (list of images, page count)
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == ".pdf":
            images = OCRProcessor.convert_pdf_to_images(file_path)
        elif file_ext in [".tiff", ".tif"]:
            images = OCRProcessor.load_tiff(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        return images, len(images)

    @staticmethod
    def process_image_paddleocr(image: Image.Image) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Extract text using PaddleOCR
        
        Args:
            image: PIL Image object
            
        Returns:
            Tuple of (text, confidence, bounding_boxes)
        """
        if not _paddleocr_available:
            raise RuntimeError("PaddleOCR not available")
        
        try:
            # Convert PIL image to CV2 format
            import cv2
            import numpy as np
            cv2_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Run OCR
            results = _paddle_ocr.ocr(cv2_image)
            
            extracted_text = ""
            bounding_boxes = []
            confidences = []
            
            if results and results[0]:
                for line in results[0]:
                    box, (text, confidence) = line
                    extracted_text += text + " "
                    confidences.append(confidence)
                    
                    # Convert box coordinates to bounding box format
                    points = box
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    
                    bounding_boxes.append({
                        "text": text,
                        "confidence": float(confidence),
                        "x_min": float(min(x_coords)),
                        "y_min": float(min(y_coords)),
                        "x_max": float(max(x_coords)),
                        "y_max": float(max(y_coords)),
                    })
            
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return extracted_text.strip(), float(overall_confidence), bounding_boxes
            
        except Exception as e:
            logger.error(f"Error processing image with PaddleOCR: {e}")
            raise

    @staticmethod
    def process_image_tesseract(image: Image.Image) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Extract text using Tesseract
        
        Args:
            image: PIL Image object
            
        Returns:
            Tuple of (text, confidence, bounding_boxes)
        """
        if not _tesseract_available:
            raise RuntimeError("Tesseract not available")
        
        try:
            # Get data with bounding boxes
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            extracted_text = ""
            bounding_boxes = []
            confidences = []
            
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                # Only include word-level results (level == 5)
                if data['level'][i] == 5:
                    text = data['text'][i].strip()
                    if text:
                        confidence = int(data['conf'][i]) / 100.0
                        
                        if confidence > 0:  # Only include detected text
                            extracted_text += text + " "
                            confidences.append(confidence)
                            
                            bounding_boxes.append({
                                "text": text,
                                "confidence": float(confidence),
                                "x_min": float(data['left'][i]),
                                "y_min": float(data['top'][i]),
                                "x_max": float(data['left'][i] + data['width'][i]),
                                "y_max": float(data['top'][i] + data['height'][i]),
                            })
            
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return extracted_text.strip(), float(overall_confidence), bounding_boxes
            
        except Exception as e:
            logger.error(f"Error processing image with Tesseract: {e}")
            raise

    @staticmethod
    def process_image(image: Image.Image, engine: str = None) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Extract text from image using specified OCR engine
        
        Args:
            image: PIL Image object
            engine: OCR engine to use (tesseract or paddleocr)
            
        Returns:
            Tuple of (text, confidence, bounding_boxes)
        """
        if engine is None:
            engine = OCR_ENGINE
        
        if engine == "paddleocr":
            if not _paddleocr_available:
                logger.warning("PaddleOCR not available, falling back to Tesseract")
                if _tesseract_available:
                    return OCRProcessor.process_image_tesseract(image)
                else:
                    raise RuntimeError("No OCR engine available")
            return OCRProcessor.process_image_paddleocr(image)
        elif engine == "tesseract":
            if not _tesseract_available:
                logger.warning("Tesseract not available, falling back to PaddleOCR")
                if _paddleocr_available:
                    return OCRProcessor.process_image_paddleocr(image)
                else:
                    raise RuntimeError("No OCR engine available")
            return OCRProcessor.process_image_tesseract(image)
        else:
            raise ValueError(f"Unknown OCR engine: {engine}")

    @staticmethod
    def process_file(file_path: str, engine: str = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Process entire file (PDF or TIFF) and extract text from all pages
        
        Args:
            file_path: Path to file
            engine: OCR engine to use
            
        Returns:
            Tuple of (list of page results, page count)
        """
        try:
            images, page_count = OCRProcessor.load_file(file_path)
            results = []
            
            for page_num, image in enumerate(images, 1):
                try:
                    text, confidence, boxes = OCRProcessor.process_image(image, engine)
                    results.append({
                        "page_number": page_num,
                        "text": text,
                        "confidence": confidence,
                        "bounding_boxes": boxes,
                    })
                    logger.info(f"Processed page {page_num} of {page_count}")
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {e}")
                    results.append({
                        "page_number": page_num,
                        "text": "",
                        "confidence": 0.0,
                        "bounding_boxes": [],
                        "error": str(e),
                    })
            
            return results, page_count
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise
