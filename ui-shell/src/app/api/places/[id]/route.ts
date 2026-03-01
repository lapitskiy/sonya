import { NextResponse } from "next/server";

function getInternalApiBase(): string {
  return process.env.SONYA_INTERNAL_API_URL || "http://api:8000";
}

export async function PUT(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = await req.text();

  const upstream = `${getInternalApiBase()}/places/${encodeURIComponent(id)}`;
  const r = await fetch(upstream, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;

  const upstream = `${getInternalApiBase()}/places/${encodeURIComponent(id)}`;
  const r = await fetch(upstream, { method: "DELETE", cache: "no-store" });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
