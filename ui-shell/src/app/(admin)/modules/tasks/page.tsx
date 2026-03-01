"use client";

import React, { useEffect, useMemo, useState } from "react";

type Task = {
  id: number;
  device_id: string;
  text: string;
  category?: string | null;
  urgent: boolean;
  important: boolean;
  status: "active" | "done" | string;
  created_at?: string | null;
  completed_at?: string | null;
};

type Category = {
  id: number;
  device_id: string;
  title: string;
};

type Quadrant = "ui" | "ni" | "un" | "nn";

function quadrantOf(t: Task): Quadrant {
  if (t.urgent && t.important) return "ui";
  if (!t.urgent && t.important) return "ni";
  if (t.urgent && !t.important) return "un";
  return "nn";
}

function flagsFromQuadrant(q: Quadrant): { urgent: boolean; important: boolean } {
  if (q === "ui") return { urgent: true, important: true };
  if (q === "ni") return { urgent: false, important: true };
  if (q === "un") return { urgent: true, important: false };
  return { urgent: false, important: false };
}

const quadrantLabel: Record<Quadrant, string> = {
  ui: "Срочно+Важно",
  ni: "Не срочно+Важно",
  un: "Срочно+Не важно",
  nn: "Не срочно+Не важно",
};

export default function TasksPage() {
  const [items, setItems] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [status, setStatus] = useState<"active" | "done">("active");
  const [q, setQ] = useState("");
  const [error, setError] = useState<string>("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const [newText, setNewText] = useState("");
  const [newQuadrant, setNewQuadrant] = useState<Quadrant>("ni");
  const [creating, setCreating] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadingCats, setLoadingCats] = useState(false);
  const [newCategory, setNewCategory] = useState("прочее");
  const [catNewTitle, setCatNewTitle] = useState("");
  const [catSavingId, setCatSavingId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams();
      if (deviceId.trim()) qs.set("device_id", deviceId.trim());
      qs.set("status", status);
      qs.set("limit", "200");
      const r = await fetch(`/api/tasks?${qs.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = (await r.json()) as { items: Task[] };
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    const did = deviceId.trim();
    if (!did) return;
    setLoadingCats(true);
    setError("");
    try {
      const qs = new URLSearchParams();
      qs.set("device_id", did);
      qs.set("limit", "200");
      const r = await fetch(`/api/task-categories?${qs.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = (await r.json()) as { items: Category[] };
      setCategories(Array.isArray(data.items) ? data.items : []);
    } catch (e: any) {
      setError(e?.message || "Ошибка категорий");
    } finally {
      setLoadingCats(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((it) => String(it.text || "").toLowerCase().includes(needle));
  }, [items, q]);

  const setQuadrant = async (taskId: number, quad: Quadrant) => {
    const { urgent, important } = flagsFromQuadrant(quad);
    setSavingId(taskId);
    setError("");
    try {
      const r = await fetch(`/api/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urgent, important }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Ошибка сохранения");
    } finally {
      setSavingId(null);
    }
  };

  const setCategory = async (taskId: number, category: string) => {
    const c = (category || "прочее").trim().toLowerCase();
    setSavingId(taskId);
    setError("");
    try {
      const r = await fetch(`/api/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: c }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
      await loadCategories();
    } catch (e: any) {
      setError(e?.message || "Ошибка категории");
    } finally {
      setSavingId(null);
    }
  };

  const markDone = async (taskId: number) => {
    setSavingId(taskId);
    setError("");
    try {
      const r = await fetch(`/api/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "done" }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
    } catch (e: any) {
      setError(e?.message || "Ошибка");
    } finally {
      setSavingId(null);
    }
  };

  const createTask = async () => {
    const text = newText.trim();
    const did = deviceId.trim();
    if (!did) return setError("Укажи device_id");
    if (!text) return setError("Текст задачи пустой");
    const { urgent, important } = flagsFromQuadrant(newQuadrant);
    const category = (newCategory || "прочее").trim().toLowerCase();
    setCreating(true);
    setError("");
    try {
      const r = await fetch(`/api/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: did, text, urgent, important, category }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setNewText("");
      if (status !== "active") setStatus("active");
      await load();
      await loadCategories();
    } catch (e: any) {
      setError(e?.message || "Ошибка создания");
    } finally {
      setCreating(false);
    }
  };

  const createCategory = async () => {
    const did = deviceId.trim();
    const title = (catNewTitle || "").trim().toLowerCase();
    if (!did) return setError("Укажи device_id");
    if (!title) return setError("Пустая категория");
    setError("");
    try {
      const r = await fetch(`/api/task-categories`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: did, title }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setCatNewTitle("");
      await loadCategories();
    } catch (e: any) {
      setError(e?.message || "Ошибка создания категории");
    }
  };

  const renameCategory = async (categoryId: number, title: string) => {
    const did = deviceId.trim();
    const newTitle = (title || "").trim().toLowerCase();
    if (!did) return setError("Укажи device_id");
    if (!newTitle) return setError("Пустое имя");
    setCatSavingId(categoryId);
    setError("");
    try {
      const r = await fetch(`/api/task-categories/${categoryId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: did, title: newTitle }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await loadCategories();
      await load();
    } catch (e: any) {
      setError(e?.message || "Ошибка переименования");
    } finally {
      setCatSavingId(null);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Задачи → {status === "active" ? "Активные" : "Архив"}</h1>

      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <div className="text-sm mb-1">device_id</div>
          <input className="border rounded px-3 py-2" value={deviceId} onChange={(e) => setDeviceId(e.target.value)} />
        </div>
        <div>
          <div className="text-sm mb-1">поиск (text)</div>
          <input className="border rounded px-3 py-2" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <div className="text-sm mb-1">статус</div>
          <select className="border rounded px-3 py-2" value={status} onChange={(e) => setStatus(e.target.value as any)}>
            <option value="active">Активные</option>
            <option value="done">Архив</option>
          </select>
        </div>
        <button className="px-4 py-2 rounded bg-brand-500 text-white disabled:opacity-60" onClick={load} disabled={loading}>
          {loading ? "Загружаю..." : "Обновить"}
        </button>
        <button className="px-4 py-2 rounded border disabled:opacity-60" onClick={loadCategories} disabled={loadingCats}>
          {loadingCats ? "..." : "Категории"}
        </button>
        {error ? <div className="text-sm text-red-600">{error}</div> : null}
      </div>

      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div className="min-w-[360px]">
          <div className="text-sm mb-1">новая задача</div>
          <input className="border rounded px-3 py-2 w-full" value={newText} onChange={(e) => setNewText(e.target.value)} />
        </div>
        <div>
          <div className="text-sm mb-1">приоритет</div>
          <select className="border rounded px-3 py-2" value={newQuadrant} onChange={(e) => setNewQuadrant(e.target.value as Quadrant)}>
            <option value="ui">{quadrantLabel.ui}</option>
            <option value="ni">{quadrantLabel.ni}</option>
            <option value="un">{quadrantLabel.un}</option>
            <option value="nn">{quadrantLabel.nn}</option>
          </select>
        </div>
        <div>
          <div className="text-sm mb-1">категория</div>
          <input className="border rounded px-3 py-2" value={newCategory} onChange={(e) => setNewCategory(e.target.value)} />
        </div>
        <button
          className="px-4 py-2 rounded border disabled:opacity-60"
          onClick={() => void createTask()}
          disabled={creating}
        >
          {creating ? "Добавляю..." : "Добавить"}
        </button>
      </div>

      <div className="border rounded p-3 mb-4">
        <div className="font-medium mb-2">Категории</div>
        <div className="flex flex-wrap gap-3 items-end mb-2">
          <div>
            <div className="text-sm mb-1">новая категория</div>
            <input className="border rounded px-3 py-2" value={catNewTitle} onChange={(e) => setCatNewTitle(e.target.value)} />
          </div>
          <button className="px-4 py-2 rounded border" onClick={() => void createCategory()}>
            Создать
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <div key={c.id} className="border rounded px-2 py-1 flex items-center gap-2">
              <span className="text-xs text-gray-600">#{c.id}</span>
              <input
                className="border rounded px-2 py-1 text-sm w-[140px]"
                defaultValue={c.title}
                onBlur={(e) => void renameCategory(c.id, e.target.value)}
                disabled={catSavingId === c.id}
              />
            </div>
          ))}
          {!loadingCats && categories.length === 0 ? <div className="text-sm text-gray-500">Пока нет</div> : null}
        </div>
      </div>

      <div className="overflow-auto border rounded">
        <table className="min-w-[980px] w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-2">device_id</th>
              <th className="text-left p-2">Задача</th>
              <th className="text-left p-2">Категория</th>
              <th className="text-left p-2">Приоритет</th>
              <th className="text-left p-2">Создано</th>
              <th className="text-left p-2">Действия</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => {
              const quad = quadrantOf(t);
              const cat = String(t.category || "прочее");
              return (
                <tr key={t.id} className="border-t">
                  <td className="p-2 whitespace-nowrap">{t.device_id}</td>
                  <td className="p-2">{t.text}</td>
                  <td className="p-2 whitespace-nowrap">
                    <select
                      className="border rounded px-2 py-1"
                      value={cat}
                      onChange={(e) => void setCategory(t.id, e.target.value)}
                      disabled={savingId === t.id}
                    >
                      {categories.map((c) => (
                        <option key={c.id} value={c.title}>
                          {c.title}
                        </option>
                      ))}
                      {!categories.some((c) => c.title === cat) ? <option value={cat}>{cat}</option> : null}
                    </select>
                  </td>
                  <td className="p-2 whitespace-nowrap">
                    <select
                      className="border rounded px-2 py-1"
                      value={quad}
                      onChange={(e) => void setQuadrant(t.id, e.target.value as Quadrant)}
                      disabled={savingId === t.id}
                    >
                      <option value="ui">{quadrantLabel.ui}</option>
                      <option value="ni">{quadrantLabel.ni}</option>
                      <option value="un">{quadrantLabel.un}</option>
                      <option value="nn">{quadrantLabel.nn}</option>
                    </select>
                  </td>
                  <td className="p-2 whitespace-nowrap">{t.created_at ? new Date(t.created_at).toLocaleString() : "-"}</td>
                  <td className="p-2 whitespace-nowrap">
                    {status === "active" ? (
                      <button
                        className="px-3 py-1 rounded border disabled:opacity-60"
                        onClick={() => void markDone(t.id)}
                        disabled={savingId === t.id}
                      >
                        {savingId === t.id ? "..." : "Выполнено"}
                      </button>
                    ) : (
                      <span className="text-gray-600">
                        {t.completed_at ? `Готово: ${new Date(t.completed_at).toLocaleString()}` : "done"}
                      </span>
                    )}
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
    </div>
  );
}

