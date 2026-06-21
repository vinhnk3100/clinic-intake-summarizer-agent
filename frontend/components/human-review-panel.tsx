"use client";

import { useState } from "react";
import { Loader2, Stethoscope } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import type { ClinicianDecision } from "@/lib/types";

interface Props {
  sessionId: string;
  onSubmit: (decision: ClinicianDecision, note: string) => void;
  submitting: boolean;
}

const DECISIONS: ClinicianDecision[] = [
  "APPROVED",
  "ESCALATE",
  "NEEDS_MORE_INFO",
];

export function HumanReviewPanel({ sessionId, onSubmit, submitting }: Props) {
  const [decision, setDecision] = useState<ClinicianDecision | "">("");
  const [note, setNote] = useState("");

  return (
    <Card className="border-amber-300 dark:border-amber-800">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Stethoscope className="size-5 text-amber-600" />
          <CardTitle>Clinician review</CardTitle>
        </div>
        <CardDescription>
          This case was routed for human review. Session{" "}
          <Badge variant="outline" className="font-mono">
            {sessionId}
          </Badge>{" "}
          is paused awaiting your decision.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Decision</Label>
          <Select
            value={decision}
            onValueChange={(v) =>
              setDecision((v ?? "") as ClinicianDecision | "")
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a decision…" />
            </SelectTrigger>
            <SelectContent>
              {DECISIONS.map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="review-note">Note</Label>
          <Textarea
            id="review-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. call cardiology now"
            className="min-h-24 resize-y"
          />
        </div>

        <Button
          onClick={() => decision && onSubmit(decision, note)}
          disabled={submitting || !decision}
          className="w-full"
        >
          {submitting ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Stethoscope className="size-4" />
          )}
          {submitting ? "Submitting review…" : "Submit review"}
        </Button>
      </CardContent>
    </Card>
  );
}
