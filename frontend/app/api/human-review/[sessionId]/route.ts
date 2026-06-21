import { NextRequest, NextResponse } from "next/server";

// Proxy: forward a clinician decision + note to the Python ambient service
// POST /human-review/{session_id} to resume a paused review.

const BACKEND = process.env.BACKEND_BASE_URL ?? "http://localhost:8080";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await ctx.params;

  let decision: unknown;
  let note: unknown;
  try {
    ({ decision, note } = await req.json());
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  if (typeof decision !== "string" || !decision) {
    return NextResponse.json(
      { error: "A 'decision' is required." },
      { status: 400 },
    );
  }

  try {
    const res = await fetch(
      `${BACKEND}/human-review/${encodeURIComponent(sessionId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, note: typeof note === "string" ? note : "" }),
        cache: "no-store",
      },
    );
    const body = await res.json().catch(() => ({}));
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json(
      {
        error: `Cannot reach the ambient backend at ${BACKEND}. Start it with \`make ambient\` (port 8080).`,
      },
      { status: 502 },
    );
  }
}
