export default function AlertBanner({ alerts }) {
  if (!alerts || alerts.length === 0) return null;

  const criticals = alerts.filter((a) => a.severity === "critical");
  const warnings = alerts.filter((a) => a.severity === "warning");

  const Icon = ({ critical }) => (
    <svg
      className={`w-4 h-4 shrink-0 ${critical ? "text-red-600" : "text-amber-600"}`}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="2"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c.866 1.5.217 3.374-1.48 3.374h-16.646c-1.697 0-2.346-1.875-1.48-3.374L10.52 3.126a2.25 2.25 0 013.96 0l8.823 15.376z"
      />
    </svg>
  );

  return (
    <div className="space-y-2">
      {criticals.map((alert, i) => (
        <div
          key={`c-${i}`}
          className="flex items-center gap-2.5 bg-red-50 ring-1 ring-red-200 text-red-700 px-4 py-2.5 rounded-xl text-sm font-semibold shadow-sm"
        >
          <span className="flex flex-col justify-center">
            <Icon critical />
          </span>
          <span className="flex-1">{alert.message}</span>
          <span className="text-[10px] font-extrabold uppercase tracking-wider bg-red-100 text-red-600 px-2 py-0.5 rounded-md">
            Critical
          </span>
        </div>
      ))}
      {warnings.map((alert, i) => (
        <div
          key={`w-${i}`}
          className="flex items-center gap-2.5 bg-amber-50 ring-1 ring-amber-200 text-amber-800 px-4 py-2.5 rounded-xl text-sm font-medium shadow-sm"
        >
          <Icon />
          <span className="flex-1">{alert.message}</span>
          <span className="text-[10px] font-extrabold uppercase tracking-wider bg-amber-100 text-amber-700 px-2 py-0.5 rounded-md">
            Review
          </span>
        </div>
      ))}
    </div>
  );
}