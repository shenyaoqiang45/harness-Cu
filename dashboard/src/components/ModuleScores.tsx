import type { ForecastModule } from "../types";

function signed(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(3)}`;
}

function ModuleBar({ score }: { score: number }) {
  const width = `${Math.min(Math.abs(score), 1) * 50}%`;
  return (
    <div className="bar" aria-hidden>
      <div className="midline" />
      {score >= 0 ? (
        <span className="pos" style={{ width }} />
      ) : (
        <span className="neg" style={{ width }} />
      )}
    </div>
  );
}

export function ModuleScores({ modules }: { modules: ForecastModule[] }) {
  if (!modules.length) return null;
  return (
    <section className="section">
      <h2>模块分数</h2>
      {modules.map((m) => (
        <div className="module-row" key={m.key}>
          <span className="name">
            {m.label}
            {m.data_gaps.length ? `（缺口 ${m.data_gaps.length}）` : ""}
          </span>
          <ModuleBar score={m.score} />
          <span
            className={`score ${m.score >= 0.2 ? "bull" : m.score <= -0.2 ? "bear" : ""}`}
            style={{
              color:
                m.score >= 0.2
                  ? "var(--bull)"
                  : m.score <= -0.2
                    ? "var(--bear)"
                    : undefined,
            }}
          >
            {signed(m.score)}
          </span>
        </div>
      ))}
    </section>
  );
}
