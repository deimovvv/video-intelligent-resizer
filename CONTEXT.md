Perfecto. Te armo una documentación extensa, clara y técnica con lo que hicimos, lo que tenemos hasta ahora, y lo que viene después. La podés usar para repasar, compartir con otro chat/paralelo o incluso como README inicial para el repo.

📚 Documentación – MediaMonks · Batch Resizer (versión actual)
1. Objetivo General de la Aplicación
Creamos una herramienta web + API para redimensionar videos en lote.
 La app permite:
Resize (FFmpeg): cambiar aspect ratio (9:16, 1:1, 16:9) con center-crop.


Tracked (Face+CSRT): reencuadre dinámico siguiendo rostros u objetos.


Tracked YOLO: reencuadre inteligente usando YOLOv8 + tracker CSRT + suavizado.


👉 El resultado siempre es un ZIP con los videos procesados en los ratios elegidos.

2. Evolución del Desarrollo
🔹 Etapa 1 – Procesamiento manual (CLI)
Scripts batch_resize_min.py, batch_reframe_track.py, batch_reframe_track_yolo.py.


Se usaba carpeta input/ con videos locales y se generaba en output/.


Ejemplo:

 python scripts/batch_resize_min.py


Pros: simple y rápido.


Contras: dependía de copiar archivos manualmente a input/.



🔹 Etapa 2 – API inicial con FastAPI
Creamos main.py con endpoints /resize y luego /jobs.


Al principio solo aceptaba videos en input/, luego evolucionó a descargar URLs.


La API gestionaba:


Descargar archivos (con requests).


Procesarlos con FFmpeg o YOLO.


Empaquetar en results.zip.


Servir el ZIP vía FileResponse.



🔹 Etapa 3 – Integración con Next.js (Frontend)
Migramos el input a URLs pegadas en un textarea en la UI.


UI hecha en Next.js + Tailwind con componentes:


Sidebar, FieldLabel, Toast, Progress.


Ahora se puede:


Pegar links de Google Drive, Dropbox o HTTP directos.


Elegir ratios (checkbox).


Elegir modo (resize, tracked, tracked_yolo).


Elegir codec (h264 o prores).


El front hace POST /jobs y luego polling a /jobs/{id} hasta que el job termine → descarga ZIP.



🔹 Etapa 4 – Mejoras recientes
Nombres de archivos únicos: al descargar varias URLs ya no se sobreescriben.


ZIP con nombre fijo (results.zip).


Barra de progreso con fases: queued → downloading → processing → zipping → done.


Cancelación de jobs: endpoint /jobs/{id}/cancel.


UI refinada: feedback en tiempo real, loader, toasts de error/éxito.



3. Tecnologías que usamos
Backend (API)
Python 3.11


FastAPI – framework API.


Uvicorn – servidor ASGI.


Requests – descargas de URLs.


FFmpeg – resize, crop, codecs.


OpenCV + Mediapipe – tracking.


Ultralytics YOLOv8 – detección de personas.


Threading – para correr jobs en background.


Zipfile – empaquetar resultados.


Frontend (UI)
Next.js 14 (App Router) – base React.


TailwindCSS – estilos.


TypeScript – tipado fuerte.


Fetch API – conexión con FastAPI.


Infraestructura
Entorno virtual (.venv): aísla dependencias Python (FastAPI, Ultralytics, etc.).


Docker: empaquetamos todo en imágenes reproducibles:


Dockerfile.full: incluye FFmpeg, YOLO, Torch.


API levantada con docker run -p 8000:8000.


Git/GitHub (pendiente): versionado, etiquetas (v0.1-demo), issues y branches.



4. Diferencias claves en el flujo
Versión
Input
Procesamiento
Output
CLI inicial
Carpeta input/ local
Script Python ejecutado manual
Carpeta output/
API simple
input/ montado
FastAPI + FFmpeg
ZIP descargable
API + Next
URLs remotas (Drive, HTTP)
API baja videos, procesa y zippea
ZIP descargado desde web


5. Lo que logramos hasta ahora
✅ Resize en lote con 3 ratios.
 ✅ Center-crop sin barras.
 ✅ Reencuadre inteligente con YOLOv8 (parámetros detect_every, ema_alpha, pan_cap_px, conf).
 ✅ Descarga múltiple de URLs.
 ✅ ZIP fijo (results.zip) descargable desde la UI.
 ✅ UI moderna y usable con progreso y cancelación.
 ✅ API servida en Docker (reproducible).

6. Qué falta / Próximos pasos
Corto plazo (demo + estabilidad)
Subir a GitHub (con README y .gitignore).


Docker Compose para levantar API + Web con un solo comando.


Mejorar errores (Drive no compartido, timeouts).


Presets YOLO en la UI (rápido vs preciso).


Paralelismo en backend (ThreadPoolExecutor) para procesar varias URLs a la vez.


Mediano plazo
Logs descargables (job.log).


Soporte para imágenes (resize, outpaint → API separada).


Autenticación básica si se comparte públicamente.


Despliegue cloud (Render, Fly.io, Vercel).


Almacenamiento externo (S3/Cloud Storage en vez de runs/ local).


Largo plazo
UI avanzada: cola de jobs, historial, presets de exportación.


API pública: clientes externos puedan integrar.


Optimización GPU (si se requiere performance real con YOLO).



7. Resumen para el equipo paralelo (API de imágenes)
👉 Lo que tienen que saber los que arranquen con imágenes:
Nuestra API de video funciona con el patrón /jobs (crear job, consultar estado, bajar ZIP).


El backend usa:


download_many(urls) → descarga.


Procesador (resize o tracked_yolo).


_zip_dir() → empaqueta.


Lo mismo se puede hacer para imágenes:


/jobs recibe URLs de imágenes.


Descarga todas.


Procesa (resize, crop, outpaint).


Devuelve results.zip.


⚡ Recomendación:
 Armar un image_api/main.py separado, con el mismo esquema de jobs.
 Así el frontend puede elegir entre Video API y Image API sin mezclarse.
 Luego se unifican si queremos.

8. Conclusión
La app ya es un Batch Video Resizer con reencuadre inteligente funcional, con:
Backend en FastAPI + FFmpeg/YOLO.


Frontend en Next.js moderno.


Docker reproducible.


Pipeline basado en jobs con progreso.


Esto es una v0.1 demo.
 Ahora tenemos dos caminos paralelos:
Pulir y escalar la API de video (GitHub, Docker Compose, despliegue, mejoras UX).


Arrancar la API de imágenes con el mismo patrón de jobs.





COMO LEVANTO HOY


1) Desarrollo simple (todo local, sin Docker)
✔️ Ideal para codar rápido en tu máquina.
Terminal A (API):
cd api
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Terminal B (WEB):
cd web
# asegúrate de tener .env.local con:
# NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm install
npm run dev

Abrís: http://localhost:3000


La web llama al API en http://127.0.0.1:8000.



2) API en Docker + WEB local
✔️ Útil si quieres aislar dependencias de la API (ffmpeg/YOLO) en un contenedor, pero seguir usando Next con HMR.
API (Docker, una sola imagen):
# desde el root del repo
docker build -f Dockerfile.full -t videoresizer:full .
docker run --rm -p 8000:8000 videoresizer:full

WEB (local):
cd web
# .env.local debe decir:
# NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm install
npm run dev

Abrís: http://localhost:3000


La web habla al API del contenedor por http://127.0.0.1:8000 (porque desde tu navegador, “127.0.0.1” es tu host, que mapea al puerto expuesto del contenedor).



3) Todo con Docker Compose (API + WEB en contenedores)
✔️ Reproducible y listo para demo/equipo. No usas npm run dev.
Tu docker-compose.yml define 2 servicios: api y web.


Dentro de la red de Compose, la WEB ve a la API como http://api:8000 (nombre de servicio).


Hacia afuera, expones puertos. Si 3000 está ocupado, puedes publicar 3001.


Ejemplo mínimo (front en 3001):
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.full
    ports:
      - "8000:8000"

  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_BASE=http://api:8000  # clave!
    depends_on:
      - api
    ports:
      - "3001:3000"  # afuera 3001 -> adentro 3000

Correr:
docker compose up --build

Abrís: http://localhost:3001


No corras npm run dev aquí; la web ya corre dentro del contenedor.


Si te aparece “port already allocated”, es que ya tienes algo en ese puerto. Solución:


O paras lo que lo usa (docker ps / docker stop <id> o cerrar tu Next local)


O cambias el puerto externo en el compose (ej. "3002:3000").


Apagar todo:
docker compose down


¿Entonces qué conviene hoy?
Si estás aún iterando UI y lógica: opción 1 o 2 (rápidas).


Si quieres usar YOLO/ffmpeg “limpio” → opción 2 (API en Docker + WEB local).


Si quieres demo limpia, un solo comando y cero instalaciones en otra máquina: opción 3 (Compose).



Tabla resumen (para pegar en tu notas)
Modo
Cómo levanto API
Cómo levanto WEB
URL navegador
NEXT_PUBLIC_API_BASE
1) Local puro
uvicorn ...:8000
npm run dev
http://localhost:3000
http://127.0.0.1:8000
2) API Docker + WEB local
docker run -p 8000:8000 videoresizer:full
npm run dev
http://localhost:3000
http://127.0.0.1:8000
3) Docker Compose ambos
docker compose up --build
(no haces nada local)
http://localhost:3001 (o el que mapees)
http://api:8000 (set en compose)


docker compose up --build cache
