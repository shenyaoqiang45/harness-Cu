export function FactorLists({
  supporting,
  suppressing,
  risks,
  invalidation,
}: {
  supporting: string[];
  suppressing: string[];
  risks: string[];
  invalidation: string[];
}) {
  const hasAny =
    supporting.length > 0 ||
    suppressing.length > 0 ||
    risks.length > 0 ||
    invalidation.length > 0;
  if (!hasAny) return null;

  return (
    <>
      {(supporting.length > 0 || suppressing.length > 0) && (
        <div className="two-col">
          {supporting.length > 0 ? (
            <section className="section">
              <h2>主要支撑</h2>
              <ul className="list">
                {supporting.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {suppressing.length > 0 ? (
            <section className="section">
              <h2>主要压制</h2>
              <ul className="list">
                {suppressing.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      )}
      {risks.length > 0 ? (
        <section className="section">
          <h2>风险提示</h2>
          <ul className="list">
            {risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {invalidation.length > 0 ? (
        <section className="section">
          <h2>判断失效条件</h2>
          <ul className="list">
            {invalidation.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
