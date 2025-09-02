'use client';

import { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from '@/components/Sidebar';
import FieldLabel from '@/components/FieldLabel';
import Toast from '@/components/Toast';
import Progress from '@/components/Progress';
import { normalizeUrl, looksLikeHttp } from '@/lib/urlNormalize';

type Mode = 'resize' | 'tracked' | 'tracked_yolo';
type Ratio = '9x16' | '1x1' | '16x9';
type Codec = 'h264' | 'prores';
type YoloModel = 'yolov8n.pt' | 'yolov8s.pt';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000';

type ApiJobStatus = {
  id?: string;
  phase: 'queued' | 'downloading' | 'processing' | 'zipping' | 'done' | 'error' | 'canceled';
  message: string;
  progress?: number;
  total_steps?: number;
  step_index?: number;
  current_file?: string | null;
  current_ratio?: string | null;
  error?: string | null;
};

type JobStatus = {
  id: string;
  phase: ApiJobStatus['phase'];
  message: string;
  progress: number;
  total_steps: number;
  step_index: number;
  current_file: string | null;
  current_ratio: string | null;
  error: string | null;
};

type CreateJobBody = {
  urls: string[];
  ratios: Ratio[];
  codec: Codec;
  mode: Mode;
  group_by_ratio: boolean;
  detect_every?: number;
  ema_alpha?: number;
  pan_cap_px?: number;
  yolo_model?: YoloModel;
  yolo_conf?: number;
};

export default function Home() {
  const [urlsText, setUrlsText] = useState('');
  const [ratios, setRatios] = useState<Ratio[]>(['9x16', '1x1', '16x9']);
  const [mode, setMode] = useState<Mode>('resize');
  const [codec, setCodec] = useState<Codec>('h264');

  // knobs YOLO
  const [detectEvery, setDetectEvery] = useState<number>(12);
  const [emaAlpha, setEmaAlpha] = useState<number>(0.08);
  const [panCapPx, setPanCapPx] = useState<number>(16);
  const [yoloModel, setYoloModel] = useState<YoloModel>('yolov8n.pt');
  const [yoloConf, setYoloConf] = useState<number>(0.35);
  const [activePreset, setActivePreset] = useState<'fast' | 'balanced' | 'accurate' | null>(null);

  // agrupado por ratio
  const [groupByRatio, setGroupByRatio] = useState<boolean>(true);

  // drive
  const [driveFolder, setDriveFolder] = useState('');

  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ open: boolean; kind: 'success' | 'error' | 'info'; message: string }>({
    open: false,
    kind: 'info',
    message: '',
  });

  const urls = useMemo(
    () => urlsText.split(/\r?\n/).map((s) => s.trim()).filter(Boolean).map(normalizeUrl),
    [urlsText]
  );

  const urlErrors = useMemo(() => {
    const errs: string[] = [];
    if (urls.length === 0) errs.push('Pegá al menos 1 URL.');
    urls.forEach((u, i) => {
      if (!looksLikeHttp(u)) errs.push(`Línea ${i + 1}: no parece URL http(s).`);
    });
    if (ratios.length === 0) errs.push('Elegí al menos 1 ratio.');
    return errs;
  }, [urls, ratios]);

  const toggleRatio = (r: Ratio) =>
    setRatios((prev) => (prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r]));

  const showToast = useCallback((kind: 'success' | 'error' | 'info', message: string) => {
    setToast({ open: true, kind, message });
  }, []);

  function clearPoll() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => {
    if (!jobId) return;

    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE}/jobs/${jobId}`, { cache: 'no-store' });
        if (!res.ok) return;
        const js: ApiJobStatus = await res.json();

        const status: JobStatus = {
          id: jobId,
          phase: js.phase,
          message: js.message,
          progress: js.progress ?? 0,
          total_steps: js.total_steps ?? 0,
          step_index: js.step_index ?? 0,
          current_file: js.current_file ?? null,
          current_ratio: js.current_ratio ?? null,
          error: js.error ?? null,
        };
        setJob(status);

        if (status.phase === 'done') {
          const dl = await fetch(`${API_BASE}/jobs/${jobId}/result`);
          if (dl.ok) {
            const blob = await dl.blob();
            downloadBlob(blob, 'results.zip');
            showToast('success', '✔️ Listo: ZIP descargado.');
          } else {
            const txt = await dl.text();
            showToast('error', txt);
          }
          clearPoll();
          setJobId(null);
          setJob(null);
        } else if (status.phase === 'error') {
          showToast('error', `Error: ${status.error || status.message}`);
          clearPoll();
          setJobId(null);
        } else if (status.phase === 'canceled') {
          showToast('info', 'Job cancelado.');
          clearPoll();
          setJobId(null);
        }
      } catch {
        // swallow polling errors
      }
    };

    tick();
    pollRef.current = setInterval(tick, 1200);
    return () => clearPoll();
  }, [jobId, showToast]);

  // -------- Presets --------
  function applyPreset(kind: 'fast' | 'balanced' | 'accurate') {
    if (kind === 'fast') {
      setDetectEvery(18);
      setEmaAlpha(0.07);
      setPanCapPx(20);
      setYoloModel('yolov8n.pt');
      setYoloConf(0.35);
    } else if (kind === 'balanced') {
      setDetectEvery(12);
      setEmaAlpha(0.08);
      setPanCapPx(16);
      setYoloModel('yolov8n.pt');
      setYoloConf(0.4);
    } else {
      setDetectEvery(8);
      setEmaAlpha(0.06);
      setPanCapPx(12);
      setYoloModel('yolov8s.pt');
      setYoloConf(0.45);
    }
    setActivePreset(kind);
  }

  async function importDriveFolder() {
    if (!driveFolder.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/expand/google_drive_folder`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ folder_url: driveFolder.trim() })
      });
      if (res.status === 501) {
        showToast('error', 'El servidor no tiene habilitado Google Drive (GDRIVE_ENABLE).');
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const js = await res.json() as { files: Array<{downloadUrl:string, name:string}>; count:number; };
      if (!js.files || js.files.length === 0) {
        showToast('info', 'La carpeta no tiene videos.');
        return;
      }
      const newUrls = js.files.map(f => f.downloadUrl);
      setUrlsText(prev => {
        const prevLines = prev.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
        const merged = [...prevLines, ...newUrls];
        const seen = new Set<string>();
        return merged.filter(u => (seen.has(u) ? false : (seen.add(u), true))).join('\n');
      });
      showToast('success', `Importadas ${js.files.length} URLs desde Drive.`);
    } catch (e: unknown) {
      showToast('error', `No se pudo leer la carpeta: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (urlErrors.length > 0) {
      showToast('error', urlErrors[0]);
      return;
    }

    setLoading(true);
    setJobId(null);
    setJob(null);
    showToast('info', 'Creando job y comenzando proceso…');

    const body: CreateJobBody = {
      urls,
      ratios,
      codec,
      mode,
      group_by_ratio: groupByRatio,
    };
    if (mode === 'tracked_yolo') {
      body.detect_every = detectEvery;
      body.ema_alpha = emaAlpha;
      body.pan_cap_px = panCapPx;
      body.yolo_model = yoloModel;
      body.yolo_conf = yoloConf;
    }

    try {
      const res = await fetch(`${API_BASE}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt);
      }
      const js: { job_id: string; status: ApiJobStatus } = await res.json();
      setJobId(js.job_id);
      setJob({
        id: js.job_id,
        phase: js.status.phase,
        message: js.status.message,
        progress: js.status.progress ?? 0,
        total_steps: js.status.total_steps ?? 0,
        step_index: js.status.step_index ?? 0,
        current_file: js.status.current_file ?? null,
        current_ratio: js.status.current_ratio ?? null,
        error: js.status.error ?? null,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      showToast('error', `Error al crear job: ${msg}`);
      setLoading(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel() {
    if (!jobId) return;
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt);
      }
      showToast('info', 'Cancelando…');
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast('error', `No se pudo cancelar: ${msg}`);
    }
  }

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const busy = !!(loading || (job && ['queued', 'downloading', 'processing', 'zipping'].includes(job.phase)));
  const phaseNice: Record<JobStatus['phase'], string> = {
    queued: 'En cola…',
    downloading: 'Descargando…',
    processing: 'Procesando…',
    zipping: 'Empaquetando…',
    done: 'Listo',
    error: 'Error',
    canceled: 'Cancelado',
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="flex">
        <Sidebar />
        <main className="flex-1">
          <div className="max-w-5xl mx-auto px-6 py-10">
            <header className="mb-8">
              <h1 className="text-3xl font-semibold tracking-tight">MediaMonks · Batch Resizer</h1>
              <p className="text-neutral-400 mt-2">Interfaz conectada a {API_BASE}</p>
            </header>

            {(busy || job) && (
              <div className="mb-5 bg-neutral-900 rounded-2xl p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm text-neutral-300">{job ? phaseNice[job.phase] : 'Iniciando…'}</div>
                    <div className="text-xs text-neutral-500">
                      {job?.message}
                      {job?.current_ratio ? ` · ratio ${job.current_ratio}` : ''}
                      {job?.current_file ? ` · ${job.current_file}` : ''}
                      {job?.total_steps ? ` · paso ${Math.min(job.step_index, job.total_steps)}/${job.total_steps}` : ''}
                    </div>
                  </div>
                  {job && ['queued', 'downloading', 'processing', 'zipping'].includes(job.phase) && (
                    <button
                      onClick={handleCancel}
                      className="rounded-lg px-3 py-2 bg-neutral-800 hover:bg-neutral-700 text-sm"
                    >
                      Cancelar
                    </button>
                  )}
                </div>
                <div className="mt-3">
                  <Progress value={job?.progress ?? 0} />
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <section className="lg:col-span-2 space-y-6">
                <div className="bg-neutral-900 rounded-2xl p-5">
                  <FieldLabel label="Importar desde carpeta de Google Drive" hint="Pegá el link a la carpeta (…/folders/<id>). Requiere GDRIVE_ENABLE y credenciales en el servidor." />
                  <div className="flex gap-3 mb-3">
                    <input
                      className="flex-1 rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                      placeholder="https://drive.google.com/drive/folders/XXXXXXXX"
                      value={driveFolder}
                      onChange={(e)=>setDriveFolder(e.target.value)}
                      disabled={busy}
                    />
                    <button
                      type="button"
                      onClick={importDriveFolder}
                      disabled={busy || !driveFolder.trim()}
                      className="rounded-lg px-4 py-2 bg-neutral-800 hover:bg-neutral-700"
                    >
                      Importar
                    </button>
                  </div>

                  <FieldLabel label="URLs (una por línea)" hint="Podés pegar varias; se renombran automáticamente si repiten nombre." />
                  <textarea
                    className="w-full h-40 rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                    placeholder={'https://example.com/video1.mp4\nhttps://example.com/video2.mp4'}
                    value={urlsText}
                    onChange={(e) => setUrlsText(e.target.value)}
                    disabled={busy}
                  />
                  <div className="mt-2 text-xs text-neutral-500">{urls.length} URL(s)</div>
                  {urlErrors.length > 0 && <div className="mt-3 text-sm text-rose-400">{urlErrors[0]}</div>}
                </div>

                <div className="bg-neutral-900 rounded-2xl p-5 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <FieldLabel label="Modo" hint="Resize = FFmpeg; Tracked YOLO = detección+seguimiento" />
                      <select
                        className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                        value={mode}
                        onChange={(e) => setMode(e.target.value as Mode)}
                        disabled={busy}
                      >
                        <option value="resize">Resize (FFmpeg)</option>
                        <option value="tracked_yolo">Tracked YOLO</option>
                      </select>
                    </div>
                    <div>
                      <FieldLabel label="Codec" hint="H.264 o ProRes (solo Resize)" />
                      <select
                        className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                        value={codec}
                        onChange={(e) => setCodec(e.target.value as Codec)}
                        disabled={busy || mode === 'tracked_yolo'}
                      >
                        <option value="h264">H.264 (MP4)</option>
                        <option value="prores">ProRes</option>
                      </select>
                    </div>
                    <div>
                      <FieldLabel label="Ratios" hint="Elegí uno o más." />
                      <div className="flex items-center gap-4 flex-wrap">
                        {(['9x16', '1x1', '16x9'] as Ratio[]).map((r) => (
                          <label key={r} className="inline-flex items-center gap-2">
                            <input
                              type="checkbox"
                              className="accent-indigo-500"
                              checked={ratios.includes(r)}
                              onChange={() => toggleRatio(r)}
                              disabled={busy}
                            />
                            <span className="text-sm">{r}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <input
                      id="gbr"
                      type="checkbox"
                      className="accent-indigo-500"
                      checked={groupByRatio}
                      onChange={(e) => setGroupByRatio(e.target.checked)}
                      disabled={busy}
                    />
                    <label htmlFor="gbr" className="text-sm">
                      Carpetas por ratio en el ZIP
                    </label>
                  </div>

                  {mode === 'tracked_yolo' && (
                    <>
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className="text-sm text-neutral-400">Presets:</span>
                        <button
                          type="button"
                          className={`text-xs rounded-lg px-3 py-1 ${
                            activePreset === 'fast' ? 'bg-indigo-600' : 'bg-neutral-800 hover:bg-neutral-700'
                          }`}
                          onClick={() => applyPreset('fast')}
                          disabled={busy}
                        >
                          Rápido
                        </button>
                        <button
                          type="button"
                          className={`text-xs rounded-lg px-3 py-1 ${
                            activePreset === 'balanced' ? 'bg-indigo-600' : 'bg-neutral-800 hover:bg-neutral-700'
                          }`}
                          onClick={() => applyPreset('balanced')}
                          disabled={busy}
                        >
                          Balanceado
                        </button>
                        <button
                          type="button"
                          className={`text-xs rounded-lg px-3 py-1 ${
                            activePreset === 'accurate' ? 'bg-indigo-600' : 'bg-neutral-800 hover:bg-neutral-700'
                          }`}
                          onClick={() => applyPreset('accurate')}
                          disabled={busy}
                        >
                          Preciso
                        </button>
                        {activePreset && <span className="text-xs text-neutral-500">({activePreset})</span>}
                      </div>

                      <div className="border-t border-neutral-800 pt-4 grid grid-cols-1 md:grid-cols-5 gap-4">
                        <div>
                          <FieldLabel label="detect_every" hint="Frames entre redetecciones (↑ = más rápido)" />
                          <input
                            type="number"
                            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                            value={detectEvery}
                            min={1}
                            onChange={(e) => {
                              setActivePreset(null);
                              setDetectEvery(parseInt(e.target.value || '1', 10));
                            }}
                            disabled={busy}
                          />
                        </div>
                        <div>
                          <FieldLabel label="ema_alpha" hint="Suavizado (0–1). Más bajo = más suave." />
                          <input
                            type="number"
                            step={0.01}
                            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                            value={emaAlpha}
                            onChange={(e) => {
                              setActivePreset(null);
                              setEmaAlpha(parseFloat(e.target.value || '0.08'));
                            }}
                            disabled={busy}
                          />
                        </div>
                        <div>
                          <FieldLabel label="pan_cap_px" hint="Límite de paneo por frame (px)" />
                          <input
                            type="number"
                            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                            value={panCapPx}
                            onChange={(e) => {
                              setActivePreset(null);
                              setPanCapPx(parseInt(e.target.value || '16', 10));
                            }}
                            disabled={busy}
                          />
                        </div>
                        <div>
                          <FieldLabel label="yolo_model" hint="n = más rápido, s = más preciso" />
                          <select
                            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                            value={yoloModel}
                            onChange={(e) => {
                              setActivePreset(null);
                              setYoloModel(e.target.value as YoloModel);
                            }}
                            disabled={busy}
                          >
                            <option value="yolov8n.pt">yolov8n.pt</option>
                            <option value="yolov8s.pt">yolov8s.pt</option>
                          </select>
                        </div>
                        <div>
                          <FieldLabel label="yolo_conf" hint="Umbral de confianza (0–1)" />
                          <input
                            type="number"
                            step={0.01}
                            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2"
                            value={yoloConf}
                            onChange={(e) => {
                              setActivePreset(null);
                              setYoloConf(parseFloat(e.target.value || '0.35'));
                            }}
                            disabled={busy}
                          />
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </section>

              <aside className="space-y-6">
                <div className="bg-neutral-900 rounded-2xl p-5">
                  <h3 className="text-lg font-medium mb-3">Acciones</h3>
                  <button
                    type="submit"
                    onClick={handleSubmit}
                    disabled={busy || urlErrors.length > 0}
                    className="w-full rounded-xl px-4 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60"
                  >
                    {busy ? 'Procesando…' : 'Procesar y descargar ZIP'}
                  </button>
                </div>
              </aside>
            </form>

            <footer className="mt-10 text-xs text-neutral-500">
              © {new Date().getFullYear()} MediaMonks · Batch Resizer
            </footer>
          </div>
        </main>
      </div>

      <Toast
        open={toast.open}
        kind={toast.kind}
        message={toast.message}
        onClose={() => setToast((t) => ({ ...t, open: false }))}
      />
    </div>
  );
}