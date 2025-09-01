\# MediaMonks · Batch Resizer



Monorepo con:

\- \*\*API\*\*: FastAPI + FFmpeg + (opcional) YOLO/CSRT.

\- \*\*WEB\*\*: Next.js (App Router) como panel para crear \*jobs\* por URL y descargar `results.zip`.



\## Quickstart



\### Backend (API)

```bash

cd api

\# activar venv si corresponde

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload



