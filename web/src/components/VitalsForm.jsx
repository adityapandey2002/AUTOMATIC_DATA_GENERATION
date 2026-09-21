import { useCallback } from "react";

const SECTIONS = [
  {
    id: "PatientDemographics",
    title: "Patient",
    subtitle: "Demographics",
    accent: "sky",
    fields: [
      { key: "Name", label: "Name", suffix: "" },
      { key: "Age", label: "Age", suffix: "yrs" },
      { key: "Language", label: "Language", suffix: "" },
    ],
  },
  {
    id: "Vitals",
    title: "Vitals",
    subtitle: "Clinical measurements",
    accent: "brand",
    fields: [
      { key: "SystolicBP", label: "Systolic BP", suffix: "mmHg" },
      { key: "DiastolicBP", label: "Diastolic BP", suffix: "mmHg" },
      { key: "WeightKG", label: "Weight", suffix: "kg" },
    ],
  },
  {
    id: "MaternalHistory",
    title: "Maternal",
    subtitle: "Obstetric history",
    accent: "violet",
    fields: [
      { key: "Gravida", label: "Gravida", suffix: "" },
      { key: "Para", label: "Para", suffix: "" },
      { key: "LastMenstrualPeriod", label: "LMP", suffix: "" },
    ],
  },
];

const ACCENT = {
  sky: {
    dot: "bg-sky-400",
    label: "text-sky-700",
    pending: "border-sky-200 bg-sky-50/60",
  },
  brand: {
    dot: "bg-brand-500",
    label: "text-brand-700",
    pending: "border-brand-200 bg-brand-50/60",
  },
  violet: {
    dot: "bg-violet-400",
    label: "text-violet-700",
    pending: "border-violet-200 bg-violet-50/60",
  },
};

function SectionIcon({ accent }) {
  const path = {
    sky: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.5 20.25a8.25 8.25 0 0112.99-6.6"
      />
    ),
    brand: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 8.25v-1.5m0 11.25v-1.5M4.5 12h1.5m12 0h1.5m-9.75 4.5l1.06 1.06m7.5-7.5L20.25 4.5M4.5 4.5l1.06 1.06"
      />
    ),
    violet: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m9.303 3.376c.866 1.5.217 3.374-1.48 3.374h-16.646c-1.697 0-2.346-1.875-1.48-3.374L10.52 3.126a2.25 2.25 0 013.96 0l8.823 15.376z"
      />
    ),
  }[accent];
  return (
    <svg
      className={`w-4 h-4 ${ACCENT[accent].label}`}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="2"
      stroke="currentColor"
    >
      {path}
    </svg>
  );
}

function FieldTile({ field, section, value, confirmed, onConfirm }) {
  const accent = ACCENT[section.accent];
  const filled = value !== null && value !== "";
  const showValue = filled ? value : "—";

  return (
    <div
      className={`rounded-xl border p-3 transition-all ${
        confirmed
          ? "border-brand-300 bg-brand-50"
          : filled
          ? accent.pending
          : "border-slate-200 bg-slate-50/60"
      }`}
    >
      <div className="flex items-center justify-between gap-1">
        <span className={`text-[10px] font-bold uppercase tracking-wider ${confirmed ? "text-brand-700" : "text-slate-500"}`}>
          {field.label}
        </span>
        {confirmed && (
          <span className="flex items-center gap-0.5 text-brand-700 text-[10px] font-bold">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="3" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            OK
          </span>
        )}
      </div>

      <div className="mt-1 flex items-baseline gap-1">
        <span
          className={`text-2xl font-extrabold tracking-tight truncate ${
            confirmed
              ? "text-brand-800"
              : filled
              ? "text-slate-800"
              : "text-slate-300"
          }`}
        >
          {showValue}
        </span>
        {field.suffix && filled && (
          <span className="text-xs font-semibold text-slate-400">{field.suffix}</span>
        )}
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

export default function VitalsForm({ vitals, onConfirm }) {
  const getValue = useCallback(
    (path, key) => vitals?.[path]?.[key] ?? null,
    [vitals]
  );
  const isConfirmed = useCallback(
    (key) => Boolean(vitals?._confirmed?.[key]),
    [vitals]
  );

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-extrabold text-slate-800 tracking-tight">
            Patient Record
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Auto-filled from the conversation · confirm to lock a value
          </p>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-500 px-2.5 py-1 rounded-full">
          MCH Register
        </span>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-4 space-y-5">
        {SECTIONS.map((section) => (
          <div key={section.id}>
            <div className="flex items-center gap-2 mb-2.5">
              <span className={`w-1.5 h-1.5 rounded-full ${ACCENT[section.accent].dot}`} />
              <h3 className="text-xs font-extrabold text-slate-700 uppercase tracking-wider">
                {section.title}
              </h3>
              <span className="text-[10px] text-slate-400 font-medium">{section.subtitle}</span>
              <div className="ml-auto flex items-center gap-1 text-slate-300">
                <SectionIcon accent={section.accent} />
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {section.fields.map((f) => (
                <FieldTile
                  key={f.key}
                  field={f}
                  section={section}
                  value={getValue(section.id, f.key)}
                  confirmed={isConfirmed(f.key)}
                  onConfirm={onConfirm}
                />
              ))}
            </div>
          </div>
        ))}

        {Object.values(vitals ?? {})
          .filter((v) => v && typeof v === "object" && v !== vitals?._confirmed)
          .flatMap((obj) => Object.values(obj))
          .every((x) => x === null || x === "") && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 py-8 text-center">
            <p className="text-sm text-slate-400">
              No vitals yet — start speaking to autofill the record.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}