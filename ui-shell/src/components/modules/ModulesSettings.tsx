"use client";

import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import Button from "@/components/ui/button/Button";
import Input from "@/components/form/input/InputField";
import Label from "@/components/form/Label";
import { getGatewayBaseUrl } from "@/lib/gateway";
import React, { useEffect, useMemo, useState } from "react";

type PluginMeta = {
  name: string;
  enabled: boolean;
  manifest: any;
};

function getToken(): string {
  return (window as any).__hubcrmAccessToken || "";
}

function tryParseJwt(token: string): any | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(payload)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export default function ModulesSettings() {
  const base = useMemo(() => getGatewayBaseUrl(), []);
  const [items, setItems] = useState<PluginMeta[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [boundedContext, setBoundedContext] = useState("");
  const [version, setVersion] = useState("1.0.0");
  const [baseUrl, setBaseUrl] = useState("http://");

  const load = async () => {
    const resp = await fetch(`${base}/plugins/_meta?enabled_only=false`, { cache: "no-store" });
    if (!resp.ok) throw new Error(`plugins meta failed: ${resp.status}`);
    setItems((await resp.json()) as PluginMeta[]);
  };

  useEffect(() => {
    (async () => {
      try {
        await load();
      } catch (e: any) {
        setError(e?.message || "failed to load modules");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onToggle = async (pluginName: string, enabled: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const token = getToken();
      const resp = await fetch(`${base}/plugins/${encodeURIComponent(pluginName)}/toggle`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(token ? { authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ enabled }),
      });
      if (!resp.ok) {
        const body = await resp.text().catch(() => "");
        throw new Error(`toggle failed: ${resp.status} ${body}`);
      }
      await load();
    } catch (e: any) {
      setError(e?.message || "toggle failed");
    } finally {
      setBusy(false);
    }
  };

  const onConnect = async () => {
    setBusy(true);
    setError(null);
    try {
      const token = getToken();
      if (!token) throw new Error("нет access_token (нужно войти через Keycloak)");
      if (!name.trim()) throw new Error("name обязателен");

      const manifest = {
        name: name.trim(),
        bounded_context: (boundedContext || name).trim(),
        version: (version || "1.0.0").trim(),
        events: { subscribes: [], publishes: [] },
        ui: {},
        api: { base_url: baseUrl.trim() },
      };

      const resp = await fetch(`${base}/plugins/${encodeURIComponent(name.trim())}`, {
        method: "PUT",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ enabled: true, manifest }),
      });
      if (!resp.ok) {
        const body = await resp.text().catch(() => "");
        throw new Error(`register failed: ${resp.status} ${body}`);
      }
      setName("");
      setBoundedContext("");
      setVersion("1.0.0");
      setBaseUrl("http://");
      await load();
    } catch (e: any) {
      setError(e?.message || "connect failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageBreadcrumb pageTitle="Настройки · Модули" />

      <div className="rounded-2xl border border-gray-200 bg-white px-5 py-7 dark:border-gray-800 dark:bg-white/[0.03] xl:px-10 xl:py-12">
        <div className="text-xs text-gray-500 dark:text-gray-400 mb-4">
          Auth:{" "}
          {(() => {
            const t = getToken();
            const p = t ? tryParseJwt(t) : null;
            return t
              ? `token ok, iss=${p?.iss || "?"}, aud=${Array.isArray(p?.aud) ? p.aud.join(",") : p?.aud || "?"}`
              : "no token";
          })()}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Здесь вы регистрируете модуль (плагин) в <span className="font-medium">plugin-registry</span>, чтобы ядро
          видело его в списке. Для <span className="font-medium">api.base_url</span> используйте DNS имя контейнера в
          docker-сети (например: <span className="font-mono">http://accounting:8000</span>).
        </div>

        {error && <div className="text-sm text-red-600 mb-4">Ошибка: {error}</div>}

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div>
            <h3 className="mb-4 font-semibold text-gray-800 text-theme-xl dark:text-white/90">Подключить модуль</h3>
            <div className="space-y-4">
              <div>
                <Label>name</Label>
                <Input value={name} onChange={(e: any) => setName(e.target.value)} placeholder="например: shipping" />
              </div>
              <div>
                <Label>bounded_context</Label>
                <Input
                  value={boundedContext}
                  onChange={(e: any) => setBoundedContext(e.target.value)}
                  placeholder="например: shipping"
                />
              </div>
              <div>
                <Label>version</Label>
                <Input value={version} onChange={(e: any) => setVersion(e.target.value)} placeholder="1.0.0" />
              </div>
              <div>
                <Label>api.base_url</Label>
                <Input
                  value={baseUrl}
                  onChange={(e: any) => setBaseUrl(e.target.value)}
                  placeholder="http://my-service:8000"
                />
              </div>
              <Button size="sm" disabled={busy} onClick={onConnect} className="w-full">
                Подключить
              </Button>
            </div>
          </div>

          <div>
            <h3 className="mb-4 font-semibold text-gray-800 text-theme-xl dark:text-white/90">Список модулей</h3>
            <div className="max-w-full overflow-x-auto">
              <table className="min-w-full">
                <thead className="border-gray-100 dark:border-gray-800 border-y">
                  <tr>
                    <th className="py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">name</th>
                    <th className="py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                      enabled
                    </th>
                    <th className="py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                      action
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {items.map((p) => (
                    <tr key={p.name}>
                      <td className="py-3 text-theme-sm text-gray-800 dark:text-white/90">{p.name}</td>
                      <td className="py-3 text-theme-sm text-gray-500 dark:text-gray-400">
                        {p.enabled ? "true" : "false"}
                      </td>
                      <td className="py-3 text-theme-sm">
                        <button
                          disabled={busy}
                          className="text-brand-600 hover:text-brand-700 dark:text-brand-400"
                          onClick={() => onToggle(p.name, !p.enabled)}
                        >
                          {p.enabled ? "выключить" : "включить"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!items.length && (
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-4">Пока нет модулей.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

