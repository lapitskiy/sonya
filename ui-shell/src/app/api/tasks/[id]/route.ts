import { NextResponse } from "next/server";

function getInternalApiBase(): string {
  return process.env.SONYA_INTERNAL_API_URL || "http://api:8000";
}

export async function PUT(req: Request, ctx: { params: { id: string } }) {
  const taskId = ctx?.params?.id;
  const upstream = `${getInternalApiBase()}/tasks/${encodeURIComponent(taskId)}`;
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

