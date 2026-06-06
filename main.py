"""
FastAPI application for OCR web service
"""
import os
import shutil
import logging
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from database import get_db, create_tables, SessionLocal
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import APP_TITLE, APP_VERSION, UPLOAD_DIR, ALLOWED_EXTENSIONS, API_PREFIX, MAX_UPLOAD_SIZE
from database import get_db, create_tables, SessionLocal
from models import (
    Document, OCRResult, BoundingBox,
    DocumentSchema, DocumentListSchema, UploadResponseSchema
)
from ocr_processor import OCRProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="OCR Web Application - Extract text from PDFs and TIFF files"
)

# Static files
app.mount("/static", StaticFiles(directory="."), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== Database Initialization ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


# ==================== Background Tasks ====================

def process_document_task(document_id: int, file_path: str):
    print("=" * 50)
    print(f"OCR TASK STARTED FOR DOCUMENT {document_id}")
    print("=" * 50)
    """Background task to process OCR for a document"""
    try:
        db_session = SessionLocal()
        document = db_session.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            logger.error(f"Document {document_id} not found")
            return
        
        # Update status to processing
        document.processing_status = "processing"
        db_session.commit()
        
        logger.info(f"Starting OCR processing for document {document_id}")
        
        # Process file
        results, page_count = OCRProcessor.process_file(file_path)
        
        # Save results to database
        for result in results:
            if "error" in result:
                document.error_message = result["error"]
                document.processing_status = "failed"
                db_session.commit()
                continue
            
            ocr_result = OCRResult(
                document_id=document_id,
                page_number=result["page_number"],
                extracted_text=result["text"],
                confidence_score=result["confidence"],
            )
            db_session.add(ocr_result)
            db_session.flush()
            
            # Add bounding boxes
            for box in result["bounding_boxes"]:
                bounding_box = BoundingBox(
                    ocr_result_id=ocr_result.id,
                    text=box["text"],
                    confidence=box["confidence"],
                    x_min=box["x_min"],
                    y_min=box["y_min"],
                    x_max=box["x_max"],
                    y_max=box["y_max"],
                )
                db_session.add(bounding_box)
        
        # Update status to completed
        document.processing_status = "completed"
        db_session.commit()
        logger.info(f"Completed OCR processing for document {document_id}")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        try:
            document = db_session.query(Document).filter(Document.id == document_id).first()
            if document:
                document.processing_status = "failed"
                document.error_message = str(e)
                db_session.commit()
        except Exception as db_error:
            logger.error(f"Error updating document status: {db_error}")
    finally:
        db_session.close()


# ==================== API Endpoints ====================

@app.get("/")
def root():
    return FileResponse("index.html")


@app.post(f"{API_PREFIX}/upload", response_model=UploadResponseSchema)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Upload PDF or TIFF file for OCR processing
    
    Args:
        file: The file to upload (PDF or TIFF)
        
    Returns:
        Upload response with document ID and status
    """
    # Validate file type
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {MAX_UPLOAD_SIZE / (1024*1024)}MB"
            )
        
        # Save file
        unique_filename = f"{datetime.utcnow().timestamp()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Create database record
        document = Document(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            processing_status="pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Add background task for OCR processing
        background_tasks.add_task(process_document_task, document.id, file_path)
        
        return UploadResponseSchema(
            message="File uploaded successfully",
            document_id=document.id,
            filename=file.filename,
            status="pending"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{API_PREFIX}/documents", response_model=list[DocumentListSchema])
async def list_documents(
    status: str = None,
    db: Session = Depends(get_db)
):
    """
    Get list of uploaded documents
    
    Args:
        status: Filter by processing status (optional)
        
    Returns:
        List of documents
    """
    query = db.query(Document)
    
    if status:
        query = query.filter(Document.processing_status == status)
    
    documents = query.order_by(Document.upload_date.desc()).all()
    return documents


@app.get(f"{API_PREFIX}/documents/{{document_id}}", response_model=DocumentSchema)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Get document details with OCR results
    
    Args:
        document_id: ID of the document
        
    Returns:
        Document with all OCR results and bounding boxes
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@app.get(f"{API_PREFIX}/documents/{{document_id}}/status")
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Get processing status of a document
    
    Args:
        document_id: ID of the document
        
    Returns:
        Processing status
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": document.id,
        "status": document.processing_status,
        "error": document.error_message,
        "upload_date": document.upload_date,
    }


@app.delete(f"{API_PREFIX}/documents/{{document_id}}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a document and all its OCR results
    
    Args:
        document_id: ID of the document to delete
        
    Returns:
        Success message
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    # Delete database record (cascades to OCR results and bounding boxes)
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}


@app.get(f"{API_PREFIX}/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    Get OCR application statistics
    
    Returns:
        Statistics about documents and processing
    """
    total_documents = db.query(Document).count()
    completed = db.query(Document).filter(Document.processing_status == "completed").count()
    processing = db.query(Document).filter(Document.processing_status == "processing").count()
    failed = db.query(Document).filter(Document.processing_status == "failed").count()
    pending = db.query(Document).filter(Document.processing_status == "pending").count()
    
    total_text = db.query(OCRResult).count()
    
    return {
        "total_documents": total_documents,
        "completed": completed,
        "processing": processing,
        "failed": failed,
        "pending": pending,
        "total_ocr_results": total_text,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
