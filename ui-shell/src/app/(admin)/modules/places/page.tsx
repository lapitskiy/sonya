"use client";

import React, { useEffect, useMemo, useState } from "react";
import "leaflet/dist/leaflet.css";

type Place = {
  id: number;
  device_id: string;
  title: string;
  lat: number;
  lon: number;
  radius_m: number;
  last_seen_at?: string | null;
};

function MapPickerModal(props: {
  open: boolean;
  title: string;
  initialLat: number;
  initialLon: number;
  onClose: () => void;
  onSelect: (lat: number, lon: number) => void;
}) {
  const { open, title, initialLat, initialLon, onClose, onSelect } = props;
  const [point, setPoint] = useState<{ lat: number; lon: number }>({ lat: initialLat, lon: initialLon });
  const mapId = useMemo(() => `map_${Math.random().toString(16).slice(2)}`, []);

  useEffect(() => {
    if (!open) return;
    setPoint({ lat: initialLat, lon: initialLon });
  }, [open, initialLat, initialLon]);

  useEffect(() => {
    if (!open) return;
    let map: any = null;
    let marker: any = null;
    let alive = true;
    (async () => {
      const mod = await import("leaflet");
      const L: any = (mod as any).default ?? mod;
      const el = document.getElementById(mapId);
      if (!el || !alive) return;

      map = L.map(el).setView([initialLat, initialLon], 16);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap contributors",
      }).addTo(map);

      const icon = L.divIcon({
        className: "sonya-place-dot",
        html: '<div style="width:12px;height:12px;border-radius:9999px;background:#ef4444;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.35)"></div>',
        iconSize: [12, 12],
        iconAnchor: [6, 6],
      });
      marker = L.marker([initialLat, initialLon], { icon }).addTo(map);

      map.on("click", (e: any) => {
        const lat = Number(e?.latlng?.lat);
        const lon = Number(e?.latlng?.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
        setPoint({ lat, lon });
        marker?.setLatLng([lat, lon]);
      });
    })();
    return () => {
      alive = false;
      try {
        map?.remove();
      } catch {
        // ignore
      }
    };
  }, [open, mapId, initialLat, initialLon]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded shadow w-full max-w-[920px]">
        <div className="p-4 border-b flex items-center justify-between">
          <div className="font-semibold">{title}</div>
          <button className="px-3 py-1 rounded border" onClick={onClose}>
            Закрыть
          </button>
        </div>
        <div className="p-4">
          <div id={mapId} className="w-full h-[420px] rounded border" />
          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="text-sm text-gray-700">
              Выбрано: <span className="font-mono">{point.lat.toFixed(6)},{point.lon.toFixed(6)}</span>
            </div>
            <button
              className="px-4 py-2 rounded bg-brand-500 text-white"
              onClick={() => onSelect(point.lat, point.lon)}
            >
              Выбрать точку
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PlacesPage() {
  const [items, setItems] = useState<Place[]>([]);
  const [loading, setLoading] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState<string>("");
  const [radiusById, setRadiusById] = useState<Record<number, number>>({});
  const [titleById, setTitleById] = useState<Record<number, string>>({});
  const [latById, setLatById] = useState<Record<number, number>>({});
  const [lonById, setLonById] = useState<Record<number, number>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [mapOpen, setMapOpen] = useState(false);
  const [mapCtx, setMapCtx] = useState<{ kind: "new" } | { kind: "edit"; placeId: number }>({ kind: "new" });

  const [newDeviceId, setNewDeviceId] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newRadius, setNewRadius] = useState(150);
  const [newLat, setNewLat] = useState<number | null>(null);
  const [newLon, setNewLon] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams();
      if (deviceId.trim()) qs.set("device_id", deviceId.trim());
      qs.set("limit", "200");
      const r = await fetch(`/api/places?${qs.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = (await r.json()) as { items: Place[] };
      const list = Array.isArray(data.items) ? data.items : [];
      setItems(list);
      setRadiusById((prev) => {
        const next = { ...prev };
        for (const p of list) next[p.id] = Number.isFinite(next[p.id]) ? next[p.id] : p.radius_m;
        return next;
      });
      setTitleById((prev) => {
        const next = { ...prev };
        for (const p of list) next[p.id] = typeof next[p.id] === "string" ? next[p.id] : p.title;
        return next;
      });
      setLatById((prev) => {
        const next = { ...prev };
        for (const p of list) next[p.id] = Number.isFinite(next[p.id]) ? next[p.id] : p.lat;
        return next;
      });
      setLonById((prev) => {
        const next = { ...prev };
        for (const p of list) next[p.id] = Number.isFinite(next[p.id]) ? next[p.id] : p.lon;
        return next;
      });
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
    return items.filter((it) => String(it.title || "").toLowerCase().includes(needle));
  }, [items, q]);

  const byId = useMemo(() => new Map(items.map((p) => [p.id, p])), [items]);

  const fmt = (n: any) => (typeof n === "number" ? n.toFixed(6) : "");

  const savePlace = async (placeId: number) => {
    const p = byId.get(placeId);
    if (!p) {
      setError("Место не найдено");
      return;
    }
    const radius_m = Math.max(10, Number(radiusById[placeId] || 150));
    const title = String(titleById[placeId] ?? "").trim();
    const lat = Number.isFinite(latById[placeId]) ? Number(latById[placeId]) : Number(p.lat);
    const lon = Number.isFinite(lonById[placeId]) ? Number(lonById[placeId]) : Number(p.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError("Некорректные координаты");
      return;
    }
    setSavingId(placeId);
    setError("");
    try {
      const r = await fetch(`/api/places/${placeId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ radius_m, title, lat, lon }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Ошибка сохранения");
    } finally {
      setSavingId(null);
    }
  };

  const deletePlace = async (p: Place) => {
    if (!confirm(`Удалить место "${p.title}"?`)) return;
    setDeletingId(p.id);
    setError("");
    try {
      const r = await fetch(`/api/places/${p.id}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Ошибка удаления");
    } finally {
      setDeletingId(null);
    }
  };

  const openMapForNew = () => {
    setMapCtx({ kind: "new" });
    setMapOpen(true);
  };

  const openMapForEdit = (placeId: number) => {
    setMapCtx({ kind: "edit", placeId });
    setMapOpen(true);
  };

  const onMapSelect = async (lat: number, lon: number) => {
    setMapOpen(false);
    if (mapCtx.kind === "new") {
      setNewLat(lat);
      setNewLon(lon);
      return;
    }
    const placeId = mapCtx.placeId;
    setLatById((m) => ({ ...m, [placeId]: lat }));
    setLonById((m) => ({ ...m, [placeId]: lon }));
    await savePlace(placeId);
  };

  const createPlace = async () => {
    const device_id = (newDeviceId || deviceId || "").trim();
    const title = newTitle.trim();
    const radius_m = Math.max(10, Number(newRadius || 150));
    const lat = Number(newLat);
    const lon = Number(newLon);
    if (!device_id) {
      setError("device_id обязателен для создания места");
      return;
    }
    if (!title) {
      setError("Название обязательно для создания места");
      return;
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError("Сначала выберите точку на карте");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const r = await fetch(`/api/places`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id, title, lat, lon, radius_m }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setNewTitle("");
      setNewLat(null);
      setNewLon(null);
      await load();
    } catch (e: any) {
      setError(e?.message || "Ошибка создания");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Места → Все места</h1>

      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <div className="text-sm mb-1">device_id</div>
          <input className="border rounded px-3 py-2" value={deviceId} onChange={(e) => setDeviceId(e.target.value)} />
        </div>
        <div>
          <div className="text-sm mb-1">поиск (title)</div>
          <input className="border rounded px-3 py-2" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <button className="px-4 py-2 rounded bg-brand-500 text-white disabled:opacity-60" onClick={load} disabled={loading}>
          {loading ? "Загружаю..." : "Обновить"}
        </button>
        {error ? <div className="text-sm text-red-600">{error}</div> : null}
      </div>

      <div className="border rounded p-4 mb-4 bg-white">
        <div className="font-semibold mb-3">Добавить место</div>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <div className="text-sm mb-1">device_id</div>
            <input
              className="border rounded px-3 py-2"
              value={newDeviceId}
              placeholder={deviceId ? `по умолчанию: ${deviceId}` : ""}
              onChange={(e) => setNewDeviceId(e.target.value)}
            />
          </div>
          <div>
            <div className="text-sm mb-1">Название</div>
            <input className="border rounded px-3 py-2 w-[260px]" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          </div>
          <div>
            <div className="text-sm mb-1">Радиус (м)</div>
            <input
              className="w-[120px] border rounded px-3 py-2"
              type="number"
              min={10}
              max={10000}
              value={newRadius}
              onChange={(e) => setNewRadius(Number(e.target.value))}
            />
          </div>
          <div className="min-w-[260px]">
            <div className="text-sm mb-1">Точка</div>
            <div className="flex items-center gap-2">
              <div className="font-mono text-sm text-gray-700">
                {newLat != null && newLon != null ? `${fmt(newLat)},${fmt(newLon)}` : "не выбрана"}
              </div>
              <button className="px-3 py-2 rounded border" onClick={openMapForNew}>
                Выбрать на карте
              </button>
            </div>
          </div>
          <button
            className="px-4 py-2 rounded bg-brand-500 text-white disabled:opacity-60"
            onClick={createPlace}
            disabled={creating}
          >
            {creating ? "Добавляю..." : "Добавить"}
          </button>
        </div>
      </div>

      <div className="overflow-auto border rounded">
        <table className="min-w-[980px] w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-2">device_id</th>
              <th className="text-left p-2">Название</th>
              <th className="text-left p-2">Координаты</th>
              <th className="text-left p-2">Радиус (м)</th>
              <th className="text-left p-2">last_seen</th>
              <th className="text-left p-2">Действия</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const v = radiusById[p.id] ?? p.radius_m;
              const latV = latById[p.id] ?? p.lat;
              const lonV = lonById[p.id] ?? p.lon;
              const google = `https://www.google.com/maps?q=${latV},${lonV}`;
              const yandex = `https://yandex.ru/maps/?pt=${lonV},${latV}&z=16&l=map`;
              return (
                <tr key={p.id} className="border-t">
                  <td className="p-2 whitespace-nowrap">{p.device_id}</td>
                  <td className="p-2 whitespace-nowrap">
                    <input
                      className="border rounded px-2 py-1 w-[320px]"
                      value={titleById[p.id] ?? p.title}
                      onChange={(e) => setTitleById((m) => ({ ...m, [p.id]: e.target.value }))}
                    />
                  </td>
                  <td className="p-2 whitespace-nowrap">
                    <span className="text-gray-700 font-mono">{fmt(latV)},{fmt(lonV)}</span>{" "}
                    <a className="text-brand-600 underline" href={yandex} target="_blank" rel="noreferrer">Яндекс</a>{" "}
                    <a className="text-brand-600 underline" href={google} target="_blank" rel="noreferrer">Google</a>
                    <button className="ml-2 text-brand-700 underline" onClick={() => openMapForEdit(p.id)}>
                      Выбрать
                    </button>
                  </td>
                  <td className="p-2">
                    <div className="flex items-center gap-3">
                      <input
                        className="w-[120px] border rounded px-2 py-1"
                        type="number"
                        min={10}
                        max={10000}
                        value={v}
                        onChange={(e) => setRadiusById((m) => ({ ...m, [p.id]: Number(e.target.value) }))}
                      />
                      <input
                        className="w-[220px]"
                        type="range"
                        min={10}
                        max={2000}
                        step={10}
                        value={v}
                        onChange={(e) => setRadiusById((m) => ({ ...m, [p.id]: Number(e.target.value) }))}
                      />
                    </div>
                  </td>
                  <td className="p-2 whitespace-nowrap">{p.last_seen_at ? new Date(p.last_seen_at).toLocaleString() : "-"}</td>
                  <td className="p-2 whitespace-nowrap">
                    <button
                      className="px-3 py-1 rounded border disabled:opacity-60"
                      onClick={() => savePlace(p.id)}
                      disabled={savingId === p.id || deletingId === p.id}
                    >
                      {savingId === p.id ? "Сохраняю..." : "Сохранить"}
                    </button>
                    <button
                      className="ml-2 px-3 py-1 rounded border border-red-300 text-red-700 disabled:opacity-60"
                      onClick={() => deletePlace(p)}
                      disabled={savingId === p.id || deletingId === p.id}
                    >
                      {deletingId === p.id ? "Удаляю..." : "Удалить"}
                    </button>
                  </td>
                </tr>
              );
            })}
            {!loading && filtered.length === 0 ? (
              <tr>
                <td className="p-3 text-gray-500" colSpan={6}>
                  Пусто
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <MapPickerModal
        open={mapOpen}
        title={mapCtx.kind === "new" ? "Выбор точки (новое место)" : `Выбор точки (место #${mapCtx.placeId})`}
        initialLat={
          mapCtx.kind === "new"
            ? Number.isFinite(Number(newLat))
              ? Number(newLat)
              : 55.751244
            : Number(latById[mapCtx.placeId] ?? byId.get(mapCtx.placeId)?.lat ?? 55.751244)
        }
        initialLon={
          mapCtx.kind === "new"
            ? Number.isFinite(Number(newLon))
              ? Number(newLon)
              : 37.618423
            : Number(lonById[mapCtx.placeId] ?? byId.get(mapCtx.placeId)?.lon ?? 37.618423)
        }
        onClose={() => setMapOpen(false)}
        onSelect={onMapSelect}
      />
    </div>
  );
}

