'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';

type Item = {
  title: string;
  content: React.ReactNode;
  defaultOpen?: boolean;
};

function AccordionItem({
  item,
  isOpen,
  onToggle,
}: {
  item: Item;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);

  // Mide el contenido para animar max-height correctamente
  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;

    const update = () => setHeight(el.scrollHeight);
    update();

    // Observa cambios de tamaño internos (por si el contenido cambia)
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [item.content]);

  return (
    <div className="border-b border-neutral-800">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between py-3 text-left hover:text-white transition"
        aria-expanded={isOpen}
      >
        <span className="font-medium">{item.title}</span>
        <span
          className={`transform transition-transform duration-300 ${
            isOpen ? 'rotate-180' : ''
          }`}
          aria-hidden="true"
        >
          ⌄
        </span>
      </button>

      {/* Contenedor animado */}
      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{
          maxHeight: isOpen ? height : 0,
          opacity: isOpen ? 1 : 0,
        }}
        aria-hidden={!isOpen}
      >
        {/* Wrapper medido (no colapsa) */}
        <div ref={contentRef} className="pb-3 text-sm text-neutral-400 pr-2">
          {item.content}
        </div>
      </div>
    </div>
  );
}

export default function Sidebar() {
  const items: Item[] = useMemo(
    () => [
      {
        title: 'Intro',
        defaultOpen: true,
        content: (
          <div className="space-y-2">
            <p>
              Herramienta para <b>redimensionar videos en lote</b> (9:16, 1:1, 16:9) con opción de
              <b> reencuadre inteligente</b> (rostro/objetos) y suavizado.
            </p>
            <p>Conectado a tu API local o contenedor Docker.</p>
          </div>
        ),
      },
      {
        title: 'Cómo funciona',
        content: (
          <div className="space-y-2">
            <ol className="list-decimal pl-5">
              <li>Pegás una o varias URLs (una por línea).</li>
              <li>
                Elegís <b>Modo</b>: <i>Resize</i>, <i>Tracked</i> o <i>Tracked YOLO</i>.
              </li>
              <li>La API procesa y devuelve un ZIP con los outputs.</li>
            </ol>
            <p className="text-xs text-neutral-500">
              Resize usa FFmpeg (scale+crop). Tracked usa MediaPipe+CSRT. Tracked YOLO usa YOLOv8.
            </p>
          </div>
        ),
      },
      {
        title: 'Parámetros',
        content: (
          <div className="space-y-2">
            <ul className="list-disc pl-5">
              <li>
                <b>Ratios</b>: formatos destino (podés elegir varios).
              </li>
              <li>
                <b>Codec</b>: H.264 (MP4) general, ProRes para post.
              </li>
              <li>
                <b>detect_every</b>: mayor = más rápido, menor = más robusto.
              </li>
              <li>
                <b>ema_alpha</b>: suavizado del foco (0–1). Más bajo = más suave.
              </li>
              <li>
                <b>YOLO</b>: modelo (n/s) y umbral <i>conf</i>.
              </li>
            </ul>
          </div>
        ),
      },
      {
        title: 'Proveedores soportados',
        content: (
          <div className="space-y-2">
            <p>Podés pegar links de:</p>
            <ul className="list-disc pl-5">
              <li>Google Drive (link de compartir habitual)</li>
              <li>Dropbox (link de compartir)</li>
              <li>OneDrive (link de compartir)</li>
              <li>HTTP/HTTPS directos</li>
            </ul>
            <p className="text-xs text-neutral-500">
              El sistema normaliza automáticamente los enlaces para descarga directa.
            </p>
          </div>
        ),
      },
      {
        title: 'FAQ',
        content: (
          <div className="space-y-2">
            <p>
              <b>¿Puedo procesar una carpeta?</b> Pegá varias URLs (una por línea). Para carpetas de
              Drive, más adelante podemos integrar la API de Drive para listar.
            </p>
            <p>
              <b>¿Archivos locales?</b> Próximo paso: subida local con preview (requiere extender backend a
              multipart).
            </p>
          </div>
        ),
      },
    ],
    []
  );

  const [open, setOpen] = useState<boolean[]>(
    () => items.map((i) => !!i.defaultOpen) // evita闪烁 al montar
  );

  return (
    <aside className="w-[320px] min-h-screen bg-neutral-900/50 border-r border-neutral-800 px-5 py-6">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-widest text-neutral-500">Panel</div>
        <div className="text-lg font-semibold">Guía & Docs</div>
      </div>

      <nav className="space-y-1">
        {items.map((item, idx) => (
          <AccordionItem
            key={idx}
            item={item}
            isOpen={open[idx]}
            onToggle={() =>
              setOpen((o) => o.map((v, i) => (i === idx ? !v : v)))
            }
          />
        ))}
      </nav>
    </aside>
  );
}
