'use client';

type PresetKey = 'fast' | 'balanced' | 'accurate';

export type Preset = {
  key: PresetKey;
  name: string;
  hint: string;
  // objetivo: a qué modo apunta el preset
  targetMode: 'tracked' | 'tracked_yolo';
  detectEvery: number;
  emaAlpha: number;
  panCapPx?: number;    // solo para YOLO
  yoloModel?: 'yolov8n.pt' | 'yolov8s.pt';
  yoloConf?: number;
};

const PRESETS: Record<PresetKey, Preset> = {
  fast: {
    key: 'fast',
    name: 'Rápido',
    hint: 'Máxima velocidad en CPU / menor precisión.',
    targetMode: 'tracked_yolo',
    detectEvery: 30,
    emaAlpha: 0.10,
    panCapPx: 20,
    yoloModel: 'yolov8n.pt',
    yoloConf: 0.25,
  },
  balanced: {
    key: 'balanced',
    name: 'Equilibrado',
    hint: 'Buen balance de suavidad/precisión/tiempo.',
    targetMode: 'tracked_yolo',
    detectEvery: 18,
    emaAlpha: 0.08,
    panCapPx: 16,
    yoloModel: 'yolov8n.pt',
    yoloConf: 0.35,
  },
  accurate: {
    key: 'accurate',
    name: 'Preciso',
    hint: 'Más estable y estricto; más lento.',
    targetMode: 'tracked_yolo',
    detectEvery: 12,
    emaAlpha: 0.06,
    panCapPx: 12,
    yoloModel: 'yolov8s.pt',
    yoloConf: 0.45,
  },
};

export default function Presets({
  disabled,
  activeKey,
  onApply,
}: {
  disabled?: boolean;
  activeKey?: PresetKey | null;
  onApply: (preset: Preset) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.values(PRESETS).map((p) => {
        const active = activeKey === p.key;
        return (
          <button
            key={p.key}
            type="button"
            disabled={disabled}
            title={p.hint}
            onClick={() => onApply(p)}
            className={[
              'rounded-xl px-3 py-2 text-sm transition border',
              active
                ? 'bg-indigo-600 border-indigo-500'
                : 'bg-neutral-800 border-neutral-700 hover:bg-neutral-700',
              disabled ? 'opacity-60 cursor-not-allowed' : '',
            ].join(' ')}
          >
            {p.name}
          </button>
        );
      })}
    </div>
  );
}
