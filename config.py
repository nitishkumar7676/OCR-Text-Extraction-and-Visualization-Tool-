"""
Configuration settings for OCR Application
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ocr_user:ocr_password@localhost:5432/ocr_db"
)

# Application Configuration
APP_TITLE = "OCR Web Application"
APP_VERSION = "1.0.0"
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# File Upload Configuration
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".pdf", ".tiff", ".tif"}
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")

# OCR Configuration
OCR_ENGINE = os.getenv("OCR_ENGINE", "paddleocr")  # "tesseract" or "paddleocr"
TESSERACT_CMD = os.getenv("TESSERACT_CMD", None)

# API Configuration
API_PREFIX = "/api/v1"
