import { useCallback } from "react";

const SECTION_ICON = {
  clipboard: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6M9 4h4a2 2 0 012 2v1h1a2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V9a2 2 0 012-2h1V6a2 2 0 012-2zm4 0v2H9V4h4z" />
  ),
  user: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.5 20.25a8.25 8.25 0 0112.99-6.6" />
  ),
  activity: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8.25v-1.5m0 11.25v-1.5M4.5 12h1.5m12 0h1.5m-9.75 4.5l1.06 1.06m7.5-7.5L20.25 4.5M4.5 4.5l1.06 1.06" />
  ),
  baby: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
  ),
  certify: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
  ),
};

function displayValue(field, value) {
  if (!value) return null;
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function FieldTile({ field, value, confirmed, onConfirm }) {
  const filled = value !== null && value !== undefined;
  const shown = filled ? displayValue(field, value) : "—";
  const wide = field?.wide;

  return (
    <div
      className={`rounded-xl border p-3 transition-all ${
        wide ? "col-span-2 md:col-span-3" : ""
      } ${
        confirmed
          ? "border-brand-300 bg-brand-50"
          : filled
          ? "border-amber-200 bg-amber-50/60"
          : "border-slate-200 bg-slate-50/60"
      }`}
    >
      <div className="flex items-center justify-between gap-1">
        <div className="min-w-0">
          <span className={`block text-[10px] font-extrabold uppercase tracking-wider truncate ${confirmed ? "text-brand-700" : "text-slate-500"}`}>
            {field.label_en}
          </span>
          <span className="block text-[10px] text-slate-400 truncate">{field.label_hi}</span>
        </div>
        {confirmed && (
          <span className="flex items-center gap-0.5 text-brand-700 text-[10px] font-bold shrink-0">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="3" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            OK
          </span>
        )}
      </div>

      <div className="mt-1">
        <span
          className={`block text-lg font-extrabold tracking-tight truncate ${
            confirmed
              ? "text-brand-800"
              : filled
              ? "text-slate-800"
              : "text-slate-300"
          }`}
          title={filled ? shown : undefined}
        >
          {shown}
        </span>
      </div>

      {filled && !confirmed && (
        <button
          onClick={() => onConfirm(field.key)}
          className="mt-2 w-full flex items-center justify-center gap-1.5 rounded-lg bg-brand-600 hover:bg-brand-700 active:scale-[0.98] text-white text-xs font-bold px-3 py-1.5 transition-all shadow-sm"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="3" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          Confirm
        </button>
      )}
    </div>
  );
}

export default function CaseSheetForm({ schema, answers, confirmed, onConfirm }) {
  const getValue = useCallback(
    (key) => answers?.[key] ?? null,
    [answers]
  );
  const isConfirmed = useCallback(
    (key) => Boolean(confirmed?.[key]),
    [confirmed]
  );

  if (!schema) return null;

  const filledCount = Object.values(answers ?? {}).filter(
    (v) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0)
  ).length;
  const confirmCount = Object.values(confirmed ?? {}).filter(Boolean).length;

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-extrabold text-slate-800 tracking-tight">
            {schema.title_en} · <span className="font-bold">{schema.title_hi}</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {schema.subtitle_en} — auto-filled from the Q&A, confirmed by the health worker
          </p>
        </div>
        <div className="hidden md:flex items-center gap-2 shrink-0">
          <span className="text-[10px] font-bold uppercase tracking-wider bg-brand-100 text-brand-700 px-2.5 py-1 rounded-full">
            {filledCount} filled
          </span>
          <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full">
            {confirmCount} confirmed
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-4 space-y-6">
        {schema.sections.map((section) => (
          <div key={section.id}>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center shadow-sm shrink-0">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                  {SECTION_ICON[section.icon]}
                </svg>
              </div>
              <div className="min-w-0">
                <h3 className="text-[13px] font-extrabold text-slate-800 leading-tight">
                  {section.title_en}
                </h3>
                <p className="text-[11px] text-slate-400 leading-tight">{section.title_hi}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {section.fields.map((f) => (
                <FieldTile
                  key={f.key}
                  field={f}
                  value={getValue(f.key)}
                  confirmed={isConfirmed(f.key)}
                  onConfirm={onConfirm}
                />
              ))}
            </div>
          </div>
        ))}

        {filledCount === 0 && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 py-8 text-center">
            <p className="text-sm font-semibold text-slate-400">
              Case sheet is empty
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Press <span className="font-bold text-brand-600">Start Recording</span> and ask the patient
              the registration questions — answers will autofill here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}