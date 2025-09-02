# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### API (FastAPI Backend)
- **Development**: `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload` (from project root)
- **Docker**: `docker-compose up` (runs both API and web services)

### Web (Next.js Frontend)
- **Development**: `npm run dev` (in web/ directory)
- **Build**: `npm run build`
- **Lint**: `npm run lint`
- **Start**: `npm start` (production)

### Docker Deployment
- **Full stack**: `docker-compose up` (uses Dockerfile.full for API, web/Dockerfile for frontend)
- **Environment variables**: Set `GDRIVE_ENABLE=1` and mount `api/sa.json` for Google Drive integration

## Architecture Overview

This is a **monorepo** containing a video batch resizing and reframing tool with two main components:

### Backend (FastAPI + Python)
- **Core API** (`api/main.py`): RESTful API handling video processing jobs
- **Video Processing Modes**:
  - `resize`: Basic FFmpeg-based resizing with aspect ratio cropping
  - `tracked_yolo`: Advanced YOLO object detection + CSRT tracking for intelligent focal point selection
- **Key Features**:
  - Asynchronous job processing with progress tracking
  - Google Drive folder integration (when `GDRIVE_ENABLE=1`)
  - Support for multiple aspect ratios (9:16, 1:1, 16:9) 
  - Multiple codecs (H.264, ProRes)
  - ZIP file delivery of processed videos

### Frontend (Next.js 15 + React 19)
- **Single Page Application** (`web/src/app/page.tsx`): Complete video processing interface
- **Tech Stack**: Next.js App Router, TypeScript, Tailwind CSS v4
- **Key Features**:
  - URL normalization for cloud storage providers (Google Drive, Dropbox, OneDrive)
  - Real-time job progress monitoring with polling
  - YOLO parameter presets (fast, balanced, accurate)
  - Toast notifications and loading states

### Video Processing Architecture

1. **Input Handling**: 
   - Supports direct HTTP URLs and cloud storage links
   - URL normalization (`web/src/lib/urlNormalize.ts`) converts sharing URLs to direct download links
   - Batch download with automatic file deduplication

2. **Processing Pipeline**:
   - **Resize mode**: Uses FFmpeg with `scale` and `crop` filters for center-cropped output
   - **YOLO Tracking mode**: Uses YOLOv8 for person detection + OpenCV CSRT tracker for smooth focal point following
   - **EMA smoothing**: Exponential moving average for smooth camera movement
   - **Pan limiting**: Configurable maximum pan speed per frame

3. **Output Management**:
   - Configurable folder structure (grouped by ratio or flat)
   - ZIP packaging with progress feedback
   - Automatic file naming with ratio suffixes

## Key Components and Files

### Backend (`api/`)
- `main.py`: Main FastAPI application with job management and endpoints
- `downloader.py`: Multi-URL download handling with cloud provider support
- Docker integration with full dependency installation (`Dockerfile.full`)

### Frontend (`web/src/`)
- `app/page.tsx`: Main application with complex form state management and API integration
- `lib/urlNormalize.ts`: Cloud storage URL conversion utilities
- `components/`: Reusable UI components (Toast, Progress, FieldLabel, Sidebar)

### Processing Scripts (`scripts/`)
- `batch_reframe_track_yolo.py`: YOLO-based intelligent video reframing with object tracking
- `batch_resize_min.py`: Basic FFmpeg resize functionality

## Processing Parameters

### YOLO Tracking Mode
- `detect_every`: Frames between YOLO detections (higher = faster, lower accuracy)
- `ema_alpha`: Smoothing factor for camera movement (0-1, lower = smoother)
- `pan_cap_px`: Maximum pan distance per frame in pixels
- `yolo_model`: Model variant (`yolov8n.pt` for speed, `yolov8s.pt` for accuracy)
- `yolo_conf`: Detection confidence threshold (0-1)

### Output Configuration  
- `ratios`: Target aspect ratios (9:16 vertical, 1:1 square, 16:9 horizontal)
- `codec`: H.264 (MP4) or ProRes (MOV) for resize mode
- `group_by_ratio`: Organize output files in subfolders by aspect ratio

## Environment Setup

### Required Dependencies
- **Python**: FastAPI, OpenCV, Ultralytics (YOLO), FFmpeg system package
- **Node.js**: Next.js 15, React 19, TypeScript, Tailwind CSS v4

### Optional Google Drive Integration
1. Set `GDRIVE_ENABLE=1` environment variable
2. Provide service account JSON at `GOOGLE_APPLICATION_CREDENTIALS` path
3. Mount credentials file in Docker: `./api/sa.json:/app/sa.json:ro`

## API Endpoints

- `POST /jobs`: Create processing job
- `GET /jobs/{id}`: Get job status and progress  
- `GET /jobs/{id}/result`: Download ZIP results
- `POST /jobs/{id}/cancel`: Cancel running job
- `POST /expand/google_drive_folder`: Extract video URLs from Google Drive folder