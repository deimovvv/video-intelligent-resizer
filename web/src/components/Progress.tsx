type Props = {
  indeterminate?: boolean;
  value?: number; // 0..100 si no es indeterminate
};

export default function Progress({ indeterminate = true, value = 0 }: Props) {
  if (indeterminate) {
    return (
      <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
        <div className="h-full w-1/3 bg-indigo-500 animate-[progress_1.2s_infinite]" />
        <style jsx>{`
          @keyframes progress {
            0% { transform: translateX(-100%); }
            50% { transform: translateX(100%); }
            100% { transform: translateX(300%); }
          }
        `}</style>
      </div>
    );
  }
  return (
    <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
      <div
        className="h-full bg-indigo-500 transition-all"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}
