'use client';

import { useEffect } from 'react';

type Props = {
  kind: 'success' | 'error' | 'info';
  message: string;
  open: boolean;
  onClose: () => void;
  autoHideMs?: number;
};

export default function Toast({ kind, message, open, onClose, autoHideMs = 4000 }: Props) {
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(onClose, autoHideMs);
    return () => clearTimeout(t);
  }, [open, autoHideMs, onClose]);

  if (!open) return null;

  const bg =
    kind === 'success' ? 'bg-emerald-600' :
    kind === 'error' ? 'bg-rose-600' :
    'bg-indigo-600';

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <div className={`${bg} text-white rounded-xl px-4 py-3 shadow-lg shadow-black/30`}>
        {message}
      </div>
    </div>
  );
}
