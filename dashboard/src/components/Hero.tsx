import type { ForecastSnapshot } from "../types";

function toneClass(score: number): string {
  if (score >= 0.2) return "bull";
  if (score <= -0.2) return "bear";
  return "";
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function signed(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(3)}`;
}

export function Hero({ data }: { data: ForecastSnapshot }) {
  return (
    <section className="section">
      <h2>当前判断</h2>
      <div className="hero-grid">
        <div className="stat">
          <span className="label">1 周</span>
          <span className={`value ${toneClass(data.total_score)}`}>
            {data.week_outlook}
          </span>
        </div>
        <div className="stat">
          <span className="label">1 月</span>
          <span className={`value ${toneClass(data.total_score)}`}>
            {data.month_outlook}
          </span>
        </div>
        <div className="stat">
          <span className="label">总分</span>
          <span className={`value ${toneClass(data.total_score)}`}>
            {signed(data.total_score)} · {data.direction}
          </span>
        </div>
        <div className="stat">
          <span className="label">置信度</span>
          <span className={`value ${data.low_confidence ? "warn" : ""}`}>
            {pct(data.confidence)}
          </span>
        </div>
        <div className="stat">
          <span className="label">数据健康度</span>
          <span className="value">{pct(data.data_health)}</span>
        </div>
      </div>
      {data.confidence_note ? <div className="note">{data.confidence_note}</div> : null}
    </section>
  );
}
