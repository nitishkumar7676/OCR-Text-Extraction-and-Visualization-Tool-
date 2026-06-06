"""
SQLAlchemy ORM models and Pydantic schemas
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from database import Base


# ==================== SQLAlchemy ORM Models ====================

class Document(Base):
    """Document model for uploaded PDF/TIFF files"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), unique=True, index=True)
    original_filename = Column(String(255))
    file_path = Column(String(500))
    file_size = Column(Integer)  # in bytes
    page_count = Column(Integer, default=1)
    upload_date = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Relationships
    ocr_results = relationship("OCRResult", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_upload_date', 'upload_date'),
        Index('idx_status', 'processing_status'),
    )


class OCRResult(Base):
    """OCR extracted text and bounding boxes"""
    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), index=True)
    page_number = Column(Integer)
    extracted_text = Column(Text)
    confidence_score = Column(Float)  # Overall confidence
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="ocr_results")
    bounding_boxes = relationship("BoundingBox", back_populates="ocr_result", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_document_id', 'document_id'),
        Index('idx_page_number', 'page_number'),
    )


class BoundingBox(Base):
    """Bounding box coordinates for each text element"""
    __tablename__ = "bounding_boxes"

    id = Column(Integer, primary_key=True, index=True)
    ocr_result_id = Column(Integer, ForeignKey("ocr_results.id"), index=True)
    text = Column(String(1000))
    confidence = Column(Float)
    x_min = Column(Float)
    y_min = Column(Float)
    x_max = Column(Float)
    y_max = Column(Float)
    
    # Relationships
    ocr_result = relationship("OCRResult", back_populates="bounding_boxes")
    
    __table_args__ = (
        Index('idx_ocr_result_id', 'ocr_result_id'),
    )


# ==================== Pydantic Response Models ====================

class BoundingBoxSchema(BaseModel):
    """Schema for bounding box response"""
    id: int
    text: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    class Config:
        from_attributes = True


class OCRResultSchema(BaseModel):
    """Schema for OCR result response"""
    id: int
    document_id: int
    page_number: int
    extracted_text: str
    confidence_score: float
    bounding_boxes: List[BoundingBoxSchema] = []
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentSchema(BaseModel):
    """Schema for document response"""
    id: int
    filename: str
    original_filename: str
    file_size: int
    page_count: int
    upload_date: datetime
    processing_status: str
    error_message: Optional[str] = None
    ocr_results: List[OCRResultSchema] = []

    class Config:
        from_attributes = True


class DocumentListSchema(BaseModel):
    """Schema for document list response"""
    id: int
    filename: str
    original_filename: str
    file_size: int
    page_count: int
    upload_date: datetime
    processing_status: str

    class Config:
        from_attributes = True


class UploadResponseSchema(BaseModel):
    """Schema for upload response"""
    message: str
    document_id: int
    filename: str
    status: str
