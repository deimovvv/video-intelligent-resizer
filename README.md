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

Esto levanta la API en http://127.0.0.1:8000 con endpoints:

POST /jobs → crear un nuevo procesamiento (resize/tracked/tracked_yolo)

GET /jobs/{id} → consultar estado de un job

GET /jobs/{id}/result → descargar ZIP (results.zip)

POST /jobs/{id}/cancel → cancelar un job en curso
