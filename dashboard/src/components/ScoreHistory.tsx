import type { HistoryPoint } from "../types";

const W = 640;
const H = 200;
const PAD = { top: 16, right: 16, bottom: 36, left: 44 };

export function ScoreHistory({ points }: { points: HistoryPoint[] }) {
  const series = points.filter(
    (p): p is HistoryPoint & { total_score: number; generated_at: string } =>
      p.total_score != null && p.generated_at != null,
  );

  if (series.length === 0) return null;

  const scores = series.map((p) => p.total_score);
  const yMin = Math.min(-1, ...scores);
  const yMax = Math.max(1, ...scores);
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const xAt = (i: number) =>
    PAD.left + (series.length === 1 ? innerW / 2 : (i / (series.length - 1)) * innerW);
  const yAt = (v: number) =>
    PAD.top + ((yMax - v) / (yMax - yMin || 1)) * innerH;

  const path = series
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.total_score).toFixed(1)}`)
    .join(" ");

  const zeroY = yAt(0);
  const ticks = [yMin, 0, yMax];

  return (
    <section className="section">
      <h2>历史总分</h2>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="历史总分折线图">
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={zeroY}
            y2={zeroY}
            stroke="var(--border)"
            strokeDasharray="4 4"
          />
          {ticks.map((t) => (
            <text
              key={t}
              x={PAD.left - 8}
              y={yAt(t) + 4}
              textAnchor="end"
              fill="var(--muted)"
              fontSize="11"
            >
              {t.toFixed(1)}
            </text>
          ))}
          <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2" />
          {series.map((p, i) => (
            <circle
              key={p.file}
              cx={xAt(i)}
              cy={yAt(p.total_score)}
              r={3.5}
              fill="var(--accent)"
            />
          ))}
          <text
            x={PAD.left}
            y={H - 10}
            fill="var(--muted)"
            fontSize="11"
          >
            {series[0].generated_at.slice(0, 10)}
          </text>
          {series.length > 1 ? (
            <text
              x={W - PAD.right}
              y={H - 10}
              textAnchor="end"
              fill="var(--muted)"
              fontSize="11"
            >
              {series[series.length - 1].generated_at.slice(0, 10)}
            </text>
          ) : null}
        </svg>
      </div>
      <div className="chart-caption">
        Source: data/forecast/history · {series.length} 次快照 · 纵轴总分 (−1~+1)
      </div>
    </section>
  );
}
