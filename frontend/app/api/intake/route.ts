import { NextRequest, NextResponse } from "next/server";

// Proxy: wrap the intake note into a Pub/Sub-style envelope with base64
// message.data and forward to the Python ambient service /pubsub/push.
// Running server-side avoids CORS. The Python agent stays the source of truth.

const BACKEND = process.env.BACKEND_BASE_URL ?? "http://localhost:8080";
const SUBSCRIPTION = "projects/demo/subscriptions/clinic-intake-sub";

export async function POST(req: NextRequest) {
  let note: unknown;
  try {
    ({ note } = await req.json());
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  if (typeof note !== "string" || !note.trim()) {
    return NextResponse.json(
      { error: "A non-empty 'note' string is required." },
      { status: 400 },
    );
  }

  const envelope = {
    message: {
      data: Buffer.from(note, "utf-8").toString("base64"),
      messageId: String(Date.now()),
    },
    subscription: SUBSCRIPTION,
  };

  try {
    const res = await fetch(`${BACKEND}/pubsub/push`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(envelope),
      cache: "no-store",
    });
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
