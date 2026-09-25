import { useEffect, useState } from "react";

function fmtAge(age) {
  return age === null || age === undefined || age === "" ? "—" : `${age} yr`;
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString();
  } catch {
    return String(iso);
  }
}

export default function PatientsList({ refreshToken }) {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetch("/api/patients")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (cancelled) return;
        setPatients(Array.isArray(data) ? data : data.patients || []);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(String(e.message || e));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-extrabold text-slate-800 tracking-tight">
            Saved Patients · <span className="font-bold">रोगी सूची</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Each saved case sheet is listed here — tap a row for full details
          </p>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider bg-brand-100 text-brand-700 px-2.5 py-1 rounded-full">
          {patients.length} saved
        </span>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-4">
        {loading && (
          <div className="py-10 text-center text-sm font-semibold text-slate-400">Loading…</div>
        )}

        {error && (
          <div className="rounded-xl bg-red-50 ring-1 ring-red-200 px-4 py-3 text-sm font-semibold text-red-700">
            Could not load patients: {error}
          </div>
        )}

        {!loading && !error && patients.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 py-10 text-center">
            <p className="text-sm font-semibold text-slate-400">No saved patients yet</p>
            <p className="text-xs text-slate-400 mt-1">
              Record a case and press <span className="font-bold text-brand-600">Save Patient</span> — it will appear here.
            </p>
          </div>
        )}

        {!loading && !error && patients.length > 0 && (
          <div className="rounded-xl border border-slate-200 overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-3 py-2.5 font-extrabold">Name</th>
                  <th className="px-3 py-2.5 font-extrabold">Wife / Daughter of</th>
                  <th className="px-3 py-2.5 font-extrabold">Age</th>
                  <th className="px-3 py-2.5 font-extrabold">Phone</th>
                  <th className="px-3 py-2.5 font-extrabold hidden md:table-cell">Address</th>
                  <th className="px-3 py-2.5 font-extrabold hidden lg:table-cell">Saved</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {patients.map((p) => (
                  <tr
                    key={p.id || p.encounter_id}
                    onClick={() => setSelected(selected?.id === p.id ? null : p)}
                    className={`cursor-pointer transition-colors ${
                      selected?.id === p.id ? "bg-brand-50" : "hover:bg-slate-50"
                    }`}
                  >
                    <td className="px-3 py-2.5 font-bold text-slate-800">{p.name || "—"}</td>
                    <td className="px-3 py-2.5 text-slate-600">{p.spouse_parent_of || "—"}</td>
                    <td className="px-3 py-2.5 text-slate-600 tabular-nums">{fmtAge(p.age)}</td>
                    <td className="px-3 py-2.5 text-slate-600 tabular-nums">{p.contact_phone || "—"}</td>
                    <td className="px-3 py-2.5 text-slate-500 truncate max-w-[180px] hidden md:table-cell">
                      {p.address || "—"}
                    </td>
                    <td className="px-3 py-2.5 text-slate-400 text-xs hidden lg:table-cell">
                      {fmtTime(p.saved_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {selected && (
          <div className="mt-4 rounded-xl border border-brand-200 bg-brand-50/50 p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-extrabold text-brand-800">
                {selected.name || "Unnamed"} — full case sheet
              </h3>
              <button
                onClick={() => setSelected(null)}
                className="text-xs font-bold text-brand-600 hover:text-brand-800"
              >
                Close
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
              {Object.entries(selected.answers || {})
                .filter(([, v]) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length))
                .map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-white ring-1 ring-slate-200 px-2.5 py-1.5">
                    <span className="block text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      {k}
                    </span>
                    <span className="block font-bold text-slate-700 truncate">
                      {Array.isArray(v) ? v.join(", ") : String(v)}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
