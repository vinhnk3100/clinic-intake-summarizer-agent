"use client";

import { AlertTriangle, ShieldAlert, ShieldCheck, CheckCircle2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import type { IntakeResponse } from "@/lib/types";

function ListField({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      {items.length ? (
        <ul className="mt-1 list-inside list-disc text-sm">
          {items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-sm text-muted-foreground">None</p>
      )}
    </div>
  );
}

function TextField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm">{value || "Not provided"}</p>
    </div>
  );
}

export function SummaryView({ data }: { data: IntakeResponse }) {
  const { summary } = data;
  const ex = summary.extraction;
  const isReview = summary.routing_decision === "HUMAN_REVIEW_REQUIRED";

  return (
    <div className="space-y-4">
      {/* Routing */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              {isReview ? (
                <ShieldAlert className="size-5 text-destructive" />
              ) : (
                <ShieldCheck className="size-5 text-emerald-600" />
              )}
              Routing decision
            </CardTitle>
            <Badge
              variant={isReview ? "destructive" : "default"}
              className={
                isReview
                  ? ""
                  : "bg-emerald-600 text-white hover:bg-emerald-600"
              }
            >
              {summary.routing_decision}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">Session:</span>{" "}
            <span className="font-mono">{data.session_id}</span>
          </p>
          {data.pending_human_review && (
            <p className="text-amber-600">Pending human review.</p>
          )}
        </CardContent>
      </Card>

      {/* Red flags */}
      {summary.red_flags.length > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>Red flags</AlertTitle>
          <AlertDescription>
            <ul className="list-inside list-disc">
              {summary.red_flags.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Clinical fields */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Clinical summary</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <TextField label="Chief complaint" value={ex.chief_complaint} />
          <TextField label="Duration" value={ex.duration} />
          <ListField label="Symptoms" items={ex.symptoms} />
          <ListField label="Medications" items={ex.medications} />
          <ListField label="Allergies" items={ex.allergies} />
          <ListField label="Medical history" items={ex.medical_history} />
          <ListField label="Missing information" items={ex.missing_information} />
          <ListField label="Suggested questions" items={ex.suggested_questions} />
          <div className="sm:col-span-2">
            <Separator className="my-1" />
            <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Clinician summary
            </p>
            <p className="mt-1 text-sm">{ex.clinician_summary}</p>
          </div>
        </CardContent>
      </Card>

      {/* Safety + PII */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Safety &amp; privacy</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              PII findings (redacted before the model)
            </p>
            {summary.pii_findings.length ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {summary.pii_findings.map((p) => (
                  <Badge key={p} variant="secondary">
                    {p}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">None detected</p>
            )}
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Safety notes
            </p>
            <p className="mt-1 text-sm">{summary.safety_notes}</p>
          </div>
        </CardContent>
      </Card>

      {/* Clinician review result */}
      {summary.clinician_review?.reviewed && (
        <Alert>
          <CheckCircle2 className="size-4 text-emerald-600" />
          <AlertTitle>Clinician review recorded</AlertTitle>
          <AlertDescription>
            <span className="font-medium">
              {summary.clinician_review.decision}
            </span>
            {summary.clinician_review.note
              ? ` — ${summary.clinician_review.note}`
              : ""}
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
