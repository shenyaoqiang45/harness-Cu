import type { ForecastAnomaly } from "../types";

export function Anomalies({ items }: { items: ForecastAnomaly[] }) {
  if (!items.length) return null;
  return (
    <section className="section">
      <h2>数据异常</h2>
      <ul className="list">
        {items.map((a, i) => (
          <li key={`${a.indicator}-${a.date}-${i}`}>
            <span className="severity">{a.severity}</span>
            <strong>{a.indicator}</strong> ({a.date}): {a.reason}
          </li>
        ))}
      </ul>
    </section>
  );
}
