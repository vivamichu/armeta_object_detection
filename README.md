# Automated Document Object Detection 
*developed in the score of a hackathon

This repository contains an end-to-end **document processing and object detection pipeline** for detecting key elements such as **QR codes, signatures, and stamps** from scanned documents and PDFs using **YOLO-based object detection**.

The system is designed for **real-world document digitization**, supporting automated PDF-to-image conversion, batch inference, and high-throughput processing.

---

## 📌 Features

- 📄 **PDF & Image Support** – Automatically converts PDFs into images for processing  
- 🔍 **Object Detection** – Detects:
  - QR codes
  - Signatures
  - Stamps
  - Squared QR variants
- ✍️ **Manual Annotation Support** – Includes curated annotations with **square QR-code bounding boxes** to improve geometric consistency and QR readability  
- ⚡ **High-Performance Inference** – Optimized for low-latency, batch document processing  
- 🧠 **YOLO-based Pipeline** – Training, validation, and inference using Ultralytics YOLO  
- 🖼️ **Visualization Tools** – Bounding box rendering and prediction inspection  

---

## 🧠 Model & Training Details

- **Architecture:** Ultralytics YOLO (custom-trained)
- **Task:** Object Detection
- **Classes:**
  - `qr`
  - `signature`
  - `stamp`
  - `stamp_q`
- **Annotation Strategy:**
  - QR codes were **manually annotated with square bounding boxes**
  - Enforced geometric consistency improves localization and downstream QR decoding

---

## 📊 Performance Metrics

**Overall Performance (Validation Set):**

| Metric | Value |
|------|------|
| Precision | **92.97%** |
| Recall | **89.98%** |
| mAP@0.5 | **92.36%** |
| mAP@0.5:0.95 | **76.29%** |

**Per-Class Highlights:**

- **QR Codes**
  - Precision: **98.7%**
  - Recall: **82.1%**
- **Stamps**
  - Precision / Recall: **96.7% / 96.7%**
- **Signatures**
  - Precision: **87.5%**

**Inference Speed (per image):**

| Stage | Time (ms) |
|-----|----------|
| Preprocessing | ~0.38 ms |
| Model Inference | **~0.81 ms** |
| Postprocessing | ~0.29 ms |

This enables **high-throughput batch processing** suitable for enterprise document workflows.

---

## 🔄 Pipeline Overview

1. **PDF to Image Conversion**
   - Multi-page PDFs are automatically converted into image frames
2. **Preprocessing**
   - Image normalization and resizing
3. **Object Detection**
   - YOLO-based inference on each page
4. **Postprocessing**
   - Bounding box filtering and confidence thresholding
5. **Visualization & Export**
   - Annotated images and structured outputs

---
