import { NextResponse } from "next/server";

function getInternalApiBase(): string {
  return process.env.SONYA_INTERNAL_API_URL || "http://api:8000";
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const qs = new URLSearchParams();
  const deviceId = url.searchParams.get("device_id") || "";
  const status = url.searchParams.get("status") || "active";
  const limit = url.searchParams.get("limit") || "200";
  const offset = url.searchParams.get("offset") || "0";
  if (deviceId) qs.set("device_id", deviceId);
  if (status) qs.set("status", status);
  qs.set("limit", limit);
  qs.set("offset", offset);

  const upstream = `${getInternalApiBase()}/tasks?${qs.toString()}`;
  const r = await fetch(upstream, { cache: "no-store" });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export async function POST(req: Request) {
  const upstream = `${getInternalApiBase()}/tasks`;
  const body = await req.text();
  const r = await fetch(upstream, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

