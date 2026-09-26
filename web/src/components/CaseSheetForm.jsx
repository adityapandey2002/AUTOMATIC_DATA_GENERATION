import { useCallback, useRef, useState } from "react";

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

function sectionIcon(name) {
  return SECTION_ICON[name] || SECTION_ICON.clipboard;
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return null;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    const n = Object.keys(value).length;
    return n ? `${n} cell${n > 1 ? "s" : ""} filled` : null;
  }
  return String(value);
}

function isEmptyValue(value) {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value) || (typeof value === "object" && value !== null)) {
    return Object.keys(value).length === 0;
  }
  return false;
}

function inputValueOf(value) {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function Editor({ field, value, onCommit, onCancel }) {
  const inputRef = useRef(null);
  const type = field?.type || "text";

  const commit = useCallback(
    (next) => {
      onCommit(field.key, next);
    },
    [field.key, onCommit]
  );

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.currentTarget.blur();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    }
  };

  if (type === "yesno") {
    const current = value === true || value === "Yes" ? "Yes" : value === false || value === "No" ? "No" : "";
    return (
      <select
        autoFocus
        ref={inputRef}
        className="w-full rounded-lg border border-brand-300 bg-white px-2 py-1.5 text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-400"
        value={current}
        onChange={(e) => {
          const v = e.target.value;
          commit(v === "" ? null : v);
        }}
        onBlur={() => onCancel()}
      >
        <option value="">—</option>
        <option value="Yes">Yes</option>
        <option value="No">No</option>
      </select>
    );
  }

  if (type === "select") {
    const options = field.options || [];
    const current = inputValueOf(value);
    return (
      <select
        autoFocus
        ref={inputRef}
        className="w-full rounded-lg border border-brand-300 bg-white px-2 py-1.5 text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-400"
        value={current}
        onChange={(e) => {
          const v = e.target.value;
          commit(v === "" ? null : v);
        }}
        onBlur={() => onCancel()}
      >
        <option value="">—</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.en}
          </option>
        ))}
      </select>
    );
  }

  if (type === "multiselect") {
    const options = field.options || [];
    const selected = Array.isArray(value) ? value : inputValueOf(value) ? inputValueOf(value).split(",").map((s) => s.trim()).filter(Boolean) : [];
    return (
      <div className="flex flex-wrap gap-1.5 py-0.5" onBlur={() => onCancel()}>
        {options.map((o) => {
          const on = selected.includes(o.value);
          return (
            <button
              key={o.value}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                const next = on ? selected.filter((v) => v !== o.value) : [...selected, o.value];
                commit(next.length ? next : null);
              }}
              className={`px-2 py-1 rounded-md text-[11px] font-bold border transition-all ${
                on
                  ? "bg-brand-600 border-brand-600 text-white"
                  : "bg-white border-slate-200 text-slate-500 hover:border-brand-300"
              }`}
            >
              {o.en}
            </button>
          );
        })}
      </div>
    );
  }

  if (type === "table") {
    const rows = field.rows || [];
    const cols = field.columns || [];
    const current =
      value && typeof value === "object" && !Array.isArray(value) ? value : {};
    const setCell = (rowKey, colKey, raw) => {
      const next = { ...current };
      const ck = `${rowKey}|${colKey}`;
      if (raw === "") delete next[ck];
      else next[ck] = raw;
      commit(Object.keys(next).length ? next : null);
    };
    return (
      <div className="py-1" onMouseDown={(e) => e.stopPropagation()}>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] border-collapse">
            <thead>
              <tr>
                <th className="text-left pr-1 pb-1 text-[10px] font-bold text-slate-400" />
                {cols.map((c) => (
                  <th key={c.key} className="px-0.5 pb-1 text-[9px] font-extrabold uppercase text-slate-400">
                    {c.label_en}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td className="pr-1 py-0.5 text-[10px] font-bold text-slate-500 whitespace-nowrap" title={r.label_hi}>
                    {r.label_en}
                  </td>
                  {cols.map((c) => {
                    const ck = `${r.key}|${c.key}`;
                    return (
                      <td key={c.key} className="px-0.5 py-0.5">
                        <input
                          defaultValue={current[ck] || ""}
                          className="w-full min-w-[46px] rounded border border-slate-200 bg-white px-1 py-0.5 text-[11px] font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-brand-400"
                          onBlur={(e) => setCell(r.key, c.key, e.target.value)}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => onCancel()}
          className="mt-1.5 rounded-md bg-brand-600 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-brand-700"
        >
          Done
        </button>
      </div>
    );
  }

  const inputType = type === "number" ? "number" : type === "date" ? "date" : type === "time" ? "time" : "text";
  return (
    <input
      autoFocus
      ref={inputRef}
      type={inputType}
      defaultValue={inputValueOf(value)}
      className="w-full rounded-lg border border-brand-300 bg-white px-2 py-1.5 text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-400"
      onKeyDown={handleKeyDown}
      onBlur={(e) => {
        const raw = e.target.value;
        if (raw === "") {
          commit(null);
        } else if (type === "number") {
          const n = Number(raw);
          commit(Number.isFinite(n) ? n : null);
        } else {
          commit(raw);
        }
      }}
    />
  );
}

function FieldTile({ field, value, onEdit }) {
  const [editing, setEditing] = useState(false);
  const filled = !isEmptyValue(value);
  const shown = displayValue(value) || "—";
  const wide = field?.wide;

  const commit = useCallback(
    (key, next) => {
      // Tables stay open while filling cells; other editors close on commit.
      if (field?.type !== "table") setEditing(false);
      onEdit(key, next);
    },
    [field?.type, onEdit]
  );

  return (
    <div
      onClick={() => !editing && setEditing(true)}
      className={`rounded-xl border p-3 transition-all cursor-text ${
        wide ? "col-span-2 md:col-span-3" : ""
      } ${
        filled
          ? "border-blue-200 bg-blue-50/70"
          : "border-slate-200 bg-slate-50/60"
      } ${editing ? "ring-2 ring-brand-400 border-brand-400" : "hover:border-brand-300"}`}
    >
      <div className="flex items-center justify-between gap-1">
        <div className="min-w-0">
          <span className={`block text-[10px] font-extrabold uppercase tracking-wider truncate ${filled ? "text-blue-700" : "text-slate-500"}`}>
            {field.label_en}
          </span>
          <span className="block text-[10px] text-slate-400 truncate">{field.label_hi}</span>
        </div>
      </div>

      <div className="mt-1">
        {editing ? (
          <Editor field={field} value={value} onCommit={commit} onCancel={() => setEditing(false)} />
        ) : (
          <span
            className={`block text-lg font-extrabold tracking-tight truncate ${
              filled ? "text-blue-800" : "text-slate-300"
            }`}
            title={filled ? shown : undefined}
          >
            {shown}
          </span>
        )}
      </div>
    </div>
  );
}

export default function CaseSheetForm({ schema, answers, onEdit, onSave, saving, saveStatus }) {
  const getValue = useCallback(
    (key) => answers?.[key] ?? null,
    [answers]
  );

  if (!schema) return null;

  const filledCount = Object.values(answers ?? {}).filter((v) => !isEmptyValue(v)).length;

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-extrabold text-slate-800 tracking-tight">
            {schema.title_en} · <span className="font-bold">{schema.title_hi}</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {schema.subtitle_en} — auto-filled by scribe
          </p>
        </div>
        <div className="hidden md:flex items-center gap-2 shrink-0">
          <span className="text-[10px] font-bold uppercase tracking-wider bg-brand-100 text-brand-700 px-2.5 py-1 rounded-full">
            {filledCount} filled
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-4 space-y-6">
        {schema.sections.map((section) => (
          <div key={section.id}>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center shadow-sm shrink-0">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                  {sectionIcon(section.icon)}
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
                  onEdit={onEdit}
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

      <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between gap-3 bg-white">
        <span className="text-xs text-slate-400 font-semibold">
          {saveStatus || `${filledCount} fields filled`}
        </span>
        <button
          onClick={onSave}
          disabled={saving || filledCount === 0}
          className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-extrabold transition-all shadow-md active:scale-[0.98] ${
            saving || filledCount === 0
              ? "bg-slate-200 text-slate-400 cursor-not-allowed"
              : "bg-brand-600 hover:bg-brand-700 text-white"
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth="2.5" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          {saving ? "Saving…" : "Save Patient"}
        </button>
      </div>
    </div>
  );
}
