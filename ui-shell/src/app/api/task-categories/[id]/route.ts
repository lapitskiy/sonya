import { NextResponse } from "next/server";

function getInternalApiBase(): string {
  return process.env.SONYA_INTERNAL_API_URL || "http://api:8000";
}

export async function PUT(req: Request, ctx: { params: { id: string } }) {
  const categoryId = ctx?.params?.id;
  const upstream = `${getInternalApiBase()}/task-categories/${encodeURIComponent(categoryId)}`;
  const body = await req.text();
  const r = await fetch(upstream, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export async function DELETE(req: Request, ctx: { params: { id: string } }) {
  const categoryId = ctx?.params?.id;
  const url = new URL(req.url);
  const deviceId = url.searchParams.get("device_id") || "";
  const qs = new URLSearchParams();
  if (deviceId) qs.set("device_id", deviceId);
  const upstream = `${getInternalApiBase()}/task-categories/${encodeURIComponent(categoryId)}?${qs.toString()}`;
  const r = await fetch(upstream, { method: "DELETE" });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

