# MediaMonks · Batch Resizer

Herramienta para **redimensionar y reencuadrar videos en lote** (aspect ratios 9:16, 1:1, 16:9) con opción de **focal point inteligente** (rostros u objetos vía YOLO/CSRT).  

Este repositorio es un **monorepo** que contiene:

- **API (FastAPI + FFmpeg + YOLO/CSRT opcional)**  
  Procesa los videos, genera los distintos formatos y empaqueta un ZIP.  
- **WEB (Next.js App Router)**  
  Interfaz gráfica para pegar URLs de videos, seleccionar modos de procesamiento y descargar resultados fácilmente.

---

## 🚀 Quickstart

### 1. Backend (API)

```bash
cd api

# activar venv si corresponde
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
