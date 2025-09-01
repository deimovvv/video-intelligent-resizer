type Props = {
  label: string;
  hint?: string;
  htmlFor?: string;
};

export default function FieldLabel({ label, hint, htmlFor }: Props) {
  return (
    <label htmlFor={htmlFor} className="block text-sm mb-2 text-neutral-300">
      <span>{label}</span>
      {hint && (
        <span
          className="ml-2 text-xs text-neutral-400 cursor-help select-none"
          title={hint}
        >
          ⓘ
        </span>
      )}
    </label>
  );
}
