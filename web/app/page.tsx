"use client";

import { useEffect, useState } from "react";

type HealthStatus = {
  status: string;
  db: string;
  version: string;
};

type CheckResult = {
  healthy: boolean;
  data?: HealthStatus;
  error?: string;
};

export default function Home() {
  const [result, setResult] = useState<CheckResult | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function checkHealth() {
      try {
        const response = await fetch("/healthz", { cache: "no-store" });
        const data = await response.json();

        if (
          !response.ok ||
          data.status !== "ok" ||
          data.db !== "ok"
        ) {
          throw new Error("API или база данных деградировали");
        }

        if (active) {
          setResult({ healthy: true, data });
          setLastChecked(new Date().toLocaleTimeString());
        }
      } catch {
        if (active) {
          setResult({
            healthy: false,
            error: "API или база данных недоступны",
          });
          setLastChecked(new Date().toLocaleTimeString());
        }
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 5000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const healthy = result?.healthy === true;

  return (
    <main
      style={{
        maxWidth: 640,
        margin: "80px auto",
        padding: 24,
        fontFamily: "Arial, sans-serif",
      }}
    >
      <h1>TriageDesk</h1>
      <p>System Health Dashboard</p>

      <section
        style={{
          marginTop: 32,
          padding: 24,
          borderRadius: 12,
          border: `2px solid ${
            result === null ? "#9ca3af" : healthy ? "#16a34a" : "#dc2626"
          }`,
          background: result === null ? "#f3f4f6" : healthy ? "#f0fdf4" : "#fef2f2",
          color: "#111827",
        }}
      >
        <h2>
          {result === null
            ? "Проверяем систему…"
            : healthy
              ? "🟢 Система работает"
              : "🔴 Система недоступна"}
        </h2>

        {result?.data && (
          <>
            <p>API: {result.data.status}</p>
            <p>Database: {result.data.db}</p>
            <p>Version: {result.data.version}</p>
          </>
        )}

        {result?.error && <p>{result.error}</p>}

        {lastChecked && <p>Последняя проверка: {lastChecked}</p>}
      </section>
    </main>
  );
}