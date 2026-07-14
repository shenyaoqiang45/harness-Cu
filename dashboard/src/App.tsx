import { useEffect, useState } from "react";
import { fetchHistory, fetchLatest } from "./api";
import { Anomalies } from "./components/Anomalies";
import { CrossValidationPanel } from "./components/CrossValidationPanel";
import { FactorLists } from "./components/FactorLists";
import { Hero } from "./components/Hero";
import { ModuleScores } from "./components/ModuleScores";
import { ScoreHistory } from "./components/ScoreHistory";
import type { ForecastSnapshot, HistoryPoint } from "./types";

export default function App() {
  const [data, setData] = useState<ForecastSnapshot | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [latest, hist] = await Promise.all([fetchLatest(), fetchHistory()]);
        if (!cancelled) {
          setData(latest);
          setHistory(hist);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <div className="error">{error}</div>;
  }
  if (!data) {
    return <div className="loading">加载预测 JSON…</div>;
  }

  return (
    <div className="app">
      <header className="header">
        <h1>伦敦铜走势 Dashboard</h1>
        <div className="meta">
          生成：{data.generated_at.replace("T", " ")}
          {data.data_cutoff ? ` · 数据截止：${data.data_cutoff}` : ""}
        </div>
      </header>

      <Hero data={data} />
      <ModuleScores modules={data.modules} />
      {data.cross_validation ? (
        <CrossValidationPanel data={data.cross_validation} />
      ) : null}
      <ScoreHistory points={history} />
      <FactorLists
        supporting={data.supporting_factors}
        suppressing={data.suppressing_factors}
        risks={data.risks}
        invalidation={data.invalidation_conditions}
      />
      <Anomalies items={data.anomalies} />
    </div>
  );
}
