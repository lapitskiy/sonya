"use client";

import React, { useEffect, useState } from "react";
import { getGatewayBaseUrl } from "@/lib/gateway";

type Variable = {
  id: number;
  scope: string;
  title: string;
  name: string;
  value_type: string;
  value: string;
  updated_at?: string | null;
};

function getToken(): string {
  return ((window as any).__hubcrmAccessToken as string) || "";
}

const TYPE_OPTIONS = ["string", "int", "float", "bool", "json"] as const;

export default function SettingsVariablesPage() {
  const [items, setItems] = useState<Variable[]>([]);
  const [status, setStatus] = useState<string>("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<Omit<Variable, "id">>({
    scope: "global",
    title: "",
    name: "",
    value_type: "string",
    value: "",
    updated_at: null,
  });

  const base = getGatewayBaseUrl();

  const load = async () => {
    try {
      const r = await fetch(`${base}/settings/variables`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!r.ok) return;
      const data = (await r.json()) as { items: Variable[] };
      setItems(data.items || []);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set =
    (k: keyof typeof form) =>
    (
      e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
    ) =>
      setForm((p) => ({ ...p, [k]: e.target.value }));

  const startCreate = () => {
    setEditingId(null);
    setForm({
      scope: "global",
      title: "",
      name: "",
      value_type: "string",
      value: "",
      updated_at: null,
    });
    setStatus("");
  };

  const startEdit = (v: Variable) => {
    setEditingId(v.id);
    setForm({
      scope: v.scope,
      title: v.title,
      name: v.name,
      value_type: v.value_type || "string",
      value: v.value || "",
      updated_at: v.updated_at ?? null,
    });
    setStatus("");
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("Сохраняю...");
    try {
      const url =
        editingId === null
          ? `${base}/settings/variables`
          : `${base}/settings/variables/${editingId}`;
      const method = editingId === null ? "POST" : "PUT";

      // Debug: helps diagnose "Ошибка сети" (CORS / wrong base URL / connectivity)
      // eslint-disable-next-line no-console
      console.info("[variables] save", { base, url, method, scope: form.scope, name: form.name });

      const title = (form.title || "").trim() || (form.name || "").trim();

      const r = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          scope: form.scope,
          title,
          name: form.name,
          value_type: form.value_type,
          value: form.value,
        }),
      });
      if (!r.ok) {
        const raw = await r.text().catch(() => "");
        // eslint-disable-next-line no-console
        console.warn("[variables] save non-2xx", { status: r.status, raw });
        let detail: unknown;
        try {
          const msg = JSON.parse(raw || "null") as any;
          detail = msg?.detail;
        } catch {
          detail = undefined;
        }
        const detailText =
          detail === undefined
            ? ""
            : typeof detail === "string"
              ? detail
              : JSON.stringify(detail);
        setStatus(detailText ? `Ошибка: ${detailText}` : `Ошибка сохранения (${r.status})`);
        return;
      }
      setStatus("Сохранено");
      await load();
      startCreate();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[variables] save network error", { base, editingId }, err);
      setStatus("Ошибка сети (см. console)");
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-6">Настройки → Переменные</h1>

      <form onSubmit={save} className="space-y-4 max-w-3xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm mb-1">Scope</label>
            <input
              className="w-full border rounded px-3 py-2"
              value={form.scope}
              onChange={set("scope")}
              placeholder="global / module / ..."
            />
          </div>
          <div>
            <label className="block text-sm mb-1">Название</label>
            <input className="w-full border rounded px-3 py-2" value={form.title} onChange={set("title")} />
          </div>
          <div>
            <label className="block text-sm mb-1">Имя</label>
            <input className="w-full border rounded px-3 py-2" value={form.name} onChange={set("name")} />
          </div>
          <div>
            <label className="block text-sm mb-1">Тип значения</label>
            <select className="w-full border rounded px-3 py-2" value={form.value_type} onChange={set("value_type")}>
              {TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm mb-1">Значение</label>
          <textarea className="w-full border rounded px-3 py-2 min-h-[90px]" value={form.value} onChange={set("value")} />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" className="px-4 py-2 rounded bg-brand-500 text-white">
            {editingId === null ? "Добавить" : "Сохранить"}
          </button>
          <button type="button" className="px-4 py-2 rounded border" onClick={startCreate}>
            Сброс
          </button>
          <div className="text-sm text-gray-600">{status}</div>
        </div>
      </form>

      <div className="mt-10">
        <h2 className="text-lg font-semibold mb-3">Все переменные</h2>
        <div className="overflow-x-auto border rounded">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3">Scope</th>
                <th className="text-left p-3">Название</th>
                <th className="text-left p-3">Имя</th>
                <th className="text-left p-3">Тип</th>
                <th className="text-left p-3">Значение</th>
                <th className="text-left p-3 w-[120px]">Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.id} className="border-t">
                  <td className="p-3 whitespace-nowrap">{v.scope}</td>
                  <td className="p-3">{v.title}</td>
                  <td className="p-3 whitespace-nowrap">{v.name}</td>
                  <td className="p-3 whitespace-nowrap">{v.value_type}</td>
                  <td className="p-3 max-w-[520px] truncate" title={v.value}>
                    {v.value}
                  </td>
                  <td className="p-3">
                    <button className="px-3 py-1 rounded border" onClick={() => startEdit(v)}>
                      Редактировать
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="p-4 text-gray-500" colSpan={6}>
                    Пока нет переменных
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

