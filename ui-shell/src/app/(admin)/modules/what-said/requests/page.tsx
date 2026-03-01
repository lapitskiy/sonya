"use client";

import React, { useEffect, useMemo, useState } from "react";

type Row = {
  id: number;
  device_id: string;
  created_at: string | null;
  payload: any;
  pending_action?: any;
};

export default function WhatSaidRequestsPage() {
  const [items, setItems] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState<string>("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams();
      if (deviceId.trim()) qs.set("device_id", deviceId.trim());
      qs.set("limit", "200");
      const r = await fetch(`/api/what-said/requests?${qs.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = (await r.json()) as { items: Row[] };
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((it) => {
      const text = String(it?.payload?.received?.text || "").toLowerCase();
      const intent = String(it?.payload?.intent?.type || "").toLowerCase();
      return text.includes(needle) || intent.includes(needle);
    });
  }, [items, q]);

  const fmt = (n: any) => (typeof n === "number" ? n.toFixed(6) : "");
  const nluPreview = (nlu: any) => {
    if (!nlu) return "";
    try {
      const s = typeof nlu === "string" ? nlu : JSON.stringify(nlu);
      return s.length > 160 ? `${s.slice(0, 160)}…` : s;
    } catch {
      return String(nlu);
    }
  };
  const pendingPreview = (pa: any) => {
    if (!pa) return "";
    try {
      const status = pa.status ? `status=${pa.status}` : "";
      const pulled = pa.pulled_at ? `pulled_at=${pa.pulled_at}` : "";
      const body = pa.payload ? JSON.stringify(pa.payload) : "";
      const s = ["pending", status, pulled, body].filter(Boolean).join(" ");
      return s.length > 220 ? `${s.slice(0, 220)}…` : s;
    } catch {
      return "pending";
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Что говорил → Все запросы</h1>

      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <div className="text-sm mb-1">device_id</div>
          <input className="border rounded px-3 py-2" value={deviceId} onChange={(e) => setDeviceId(e.target.value)} />
        </div>
        <div>
          <div className="text-sm mb-1">поиск (text / intent)</div>
          <input className="border rounded px-3 py-2" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <button
          className="px-4 py-2 rounded bg-brand-500 text-white disabled:opacity-60"
          onClick={load}
          disabled={loading}
        >
          {loading ? "Загружаю..." : "Обновить"}
        </button>
        {error ? <div className="text-sm text-red-600">{error}</div> : null}
      </div>

      <div className="overflow-auto border rounded">
        <table className="min-w-[900px] w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-2">Дата</th>
              <th className="text-left p-2">device_id</th>
              <th className="text-left p-2">Текст</th>
              <th className="text-left p-2">Intent</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((it) => (
              <tr key={it.id} className="border-t">
                <td className="p-2 whitespace-nowrap">{it.created_at ? new Date(it.created_at).toLocaleString() : "-"}</td>
                <td className="p-2 whitespace-nowrap">{it.device_id}</td>
                <td className="p-2">
                  <div>{String(it?.payload?.received?.text || "")}</div>
                  <div className="text-xs text-gray-600 mt-1">{nluPreview(it?.payload?.nlu)}</div>
                  <div className="text-xs text-gray-600 mt-1">{pendingPreview((it as any)?.pending_action)}</div>
                </td>
                <td className="p-2 whitespace-nowrap">
                  {(() => {
                    const type = String(it?.payload?.intent?.type || "");
                    if (type !== "geo") return type;
                    const lat = it?.payload?.intent?.location?.lat;
                    const lon = it?.payload?.intent?.location?.lon;
                    if (typeof lat !== "number" || typeof lon !== "number") return "geo";
                    const google = `https://www.google.com/maps?q=${lat},${lon}`;
                    const yandex = `https://yandex.ru/maps/?pt=${lon},${lat}&z=16&l=map`;
                    return (
                      <div className="flex items-center gap-2">
                        <span>geo</span>
                        <span className="text-gray-600">{fmt(lat)},{fmt(lon)}</span>
                        <a className="text-brand-600 underline" href={yandex} target="_blank" rel="noreferrer">
                          Яндекс
                        </a>
                        <a className="text-brand-600 underline" href={google} target="_blank" rel="noreferrer">
                          Google
                        </a>
                      </div>
                    );
                  })()}
                </td>
              </tr>
            ))}
            {!loading && filtered.length === 0 ? (
              <tr>
                <td className="p-3 text-gray-500" colSpan={4}>
                  Пусто
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

