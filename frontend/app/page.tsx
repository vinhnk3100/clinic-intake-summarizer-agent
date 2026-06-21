"use client";

import { useState } from "react";
import { Activity, AlertCircle, FileText } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { IntakeForm } from "@/components/intake-form";
import { SummaryView } from "@/components/summary-view";
import { HumanReviewPanel } from "@/components/human-review-panel";
import { JsonPanel } from "@/components/json-panel";
import { SAMPLE_CASES } from "@/lib/sample-cases";
import type {
  ApiError,
  ClinicianDecision,
  IntakeResponse,
  ReviewResponse,
} from "@/lib/types";

const APP_NAME =
  process.env.NEXT_PUBLIC_APP_NAME ?? "Clinic Intake Summarizer";

export default function Home() {
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [response, setResponse] = useState<IntakeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function selectCase(id: string) {
    const c = SAMPLE_CASES.find((x) => x.id === id);
    if (c) setNote(c.note);
  }

  async function submitIntake() {
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const res = await fetch("/api/intake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
      const body = (await res.json()) as IntakeResponse & ApiError;
      if (!res.ok) {
        setError(body.error || body.detail || `Request failed (${res.status}).`);
      } else {
        setResponse(body);
      }
    } catch {
      setError("Network error calling /api/intake.");
    } finally {
      setLoading(false);
    }
  }

  async function submitReview(decision: ClinicianDecision, reviewNote: string) {
    if (!response) return;
    setReviewing(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/human-review/${encodeURIComponent(response.session_id)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision, note: reviewNote }),
        },
      );
      const body = (await res.json()) as ReviewResponse & ApiError;
      if (!res.ok) {
        setError(body.error || body.detail || `Review failed (${res.status}).`);
      } else {
        setResponse({
          ...response,
          pending_human_review: false,
          summary: body.summary,
        });
      }
    } catch {
      setError("Network error calling /api/human-review.");
    } finally {
      setReviewing(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity className="size-6 text-emerald-600" />
          <h1 className="text-xl font-semibold">{APP_NAME}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">Local demo</Badge>
          <Badge variant="secondary">Synthetic data only</Badge>
        </div>
      </header>

      <p className="mb-6 text-sm text-muted-foreground">
        Demo UI for the Clinic Intake Summarizer Agent. The Python ADK agent is
        the source of truth — this UI calls the ambient service via a server-side
        proxy. Not a medical device; a clinician reviews every flagged case.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <IntakeForm
            note={note}
            onNoteChange={setNote}
            onSelectCase={selectCase}
            onSubmit={submitIntake}
            loading={loading}
          />

          {error && (
            <Alert variant="destructive">
              <AlertCircle className="size-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {response?.pending_human_review && (
            <HumanReviewPanel
              sessionId={response.session_id}
              onSubmit={submitReview}
              submitting={reviewing}
            />
          )}
        </div>

        <div className="space-y-4">
          {response ? (
            <>
              <SummaryView data={response} />
              <JsonPanel data={response} />
            </>
          ) : (
            <div className="flex h-full min-h-64 flex-col items-center justify-center rounded-lg border border-dashed text-center text-muted-foreground">
              <FileText className="mb-2 size-8" />
              <p className="text-sm">
                Submit an intake note to see the structured summary.
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
