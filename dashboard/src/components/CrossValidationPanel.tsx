import type { CrossValidation } from "../types";

function signed(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(3)}`;
}

export function CrossValidationPanel({ data }: { data: CrossValidation }) {
  return (
    <section className="section">
      <h2>A/B 交叉验证</h2>
      <p style={{ margin: "0 0 12px", fontSize: "0.92rem" }}>
        <strong>{data.agreement}</strong>
        {data.note ? ` · ${data.note}` : ""}
      </p>
      <table className="table">
        <thead>
          <tr>
            <th>组别</th>
            <th>分数</th>
            <th>方向</th>
          </tr>
        </thead>
        <tbody>
          {data.groups.map((g) => (
            <tr key={g.name}>
              <td>{g.label}</td>
              <td className="num">{signed(g.score)}</td>
              <td>{g.direction}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
