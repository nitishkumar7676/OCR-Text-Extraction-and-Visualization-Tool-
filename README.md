OCR Web Application
Overview

This project is a Python-based OCR (Optical Character Recognition) web application that allows users to upload PDF and TIFF documents, extract text and bounding box coordinates using Tesseract OCR, store the extracted data in PostgreSQL, and display the results in a user-friendly web interface.


Tech Stack:
- FastAPI
- PostgreSQL
- Tesseract OCR
- HTML/CSS/JavaScript

Features:
- Upload PDF/TIFF files
- Extract text using OCR
- Extract bounding box coordinates
- Store results in PostgreSQL
- Display OCR results in UI

Setup:
1. Install Python dependencies
2. Install PostgreSQL
3. Install Tesseract OCR
4. Configure .env
5. Run:
   uvicorn main:app --reload
