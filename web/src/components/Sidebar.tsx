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

  // Measure content to animate max-height correctly
  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;

    const update = () => setHeight(el.scrollHeight);
    update();

    // Observe internal size changes (in case content changes)
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
        suppressHydrationWarning
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

      {/* Animated container */}
      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{
          maxHeight: isOpen ? height : 0,
          opacity: isOpen ? 1 : 0,
        }}
        aria-hidden={!isOpen}
      >
        {/* Measured wrapper (doesn't collapse) */}
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
              Tool for <b>batch video resizing</b> (9:16, 1:1, 16:9) with option for
              <b> intelligent reframing</b> (face/objects) and smoothing.
            </p>
            <p>Connected to your local API or Docker container.</p>
          </div>
        ),
      },
      {
        title: 'How it works',
        content: (
          <div className="space-y-2">
            <ol className="list-decimal pl-5">
              <li>Paste one or multiple URLs (one per line).</li>
              <li>
                Choose <b>Mode</b>: <i>Resize</i>, <i>Tracked</i> or <i>Tracked YOLO</i>.
              </li>
              <li>The API processes and returns a ZIP with the outputs.</li>
            </ol>
            <p className="text-xs text-neutral-500">
              Resize uses FFmpeg (scale+crop). Tracked uses MediaPipe+CSRT. Tracked YOLO uses YOLOv8.
            </p>
          </div>
        ),
      },
      {
        title: 'Parameters',
        content: (
          <div className="space-y-2">
            <ul className="list-disc pl-5">
              <li>
                <b>Ratios</b>: target formats (you can choose multiple).
              </li>
              <li>
                <b>Codec</b>: H.264 (MP4) general, ProRes for post.
              </li>
              <li>
                <b>detect_every</b>: higher = faster, lower = more robust.
              </li>
              <li>
                <b>ema_alpha</b>: focus smoothing (0–1). Lower = smoother.
              </li>
              <li>
                <b>YOLO</b>: model (n/s) and <i>conf</i> threshold.
              </li>
            </ul>
          </div>
        ),
      },
      {
        title: 'Supported providers',
        content: (
          <div className="space-y-2">
            <p>You can paste links from:</p>
            <ul className="list-disc pl-5">
              <li>Google Drive (regular sharing link)</li>
              <li>Dropbox (sharing link)</li>
              <li>OneDrive (sharing link)</li>
              <li>Direct HTTP/HTTPS</li>
            </ul>
            <p className="text-xs text-neutral-500">
              The system automatically normalizes links for direct download.
            </p>
          </div>
        ),
      },
      {
        title: 'FAQ',
        content: (
          <div className="space-y-2">
            <p>
              <b>Can I process a folder?</b> Paste multiple URLs (one per line). For Drive folders,
              we can later integrate the Drive API for listing.
            </p>
            <p>
              <b>Local files?</b> Next step: local upload with preview (requires extending backend to
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
        <div className="text-lg font-semibold">Guide & Docs</div>
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
