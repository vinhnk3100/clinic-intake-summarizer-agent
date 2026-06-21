"use client";

import { Send, Loader2 } from "lucide-react";
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
import { SAMPLE_CASES } from "@/lib/sample-cases";

interface Props {
  note: string;
  onNoteChange: (note: string) => void;
  onSelectCase: (id: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function IntakeForm({
  note,
  onNoteChange,
  onSelectCase,
  onSubmit,
  loading,
}: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Patient intake note</CardTitle>
        <CardDescription>
          Pick a sample case or edit the note, then submit to the agent.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Sample case</Label>
          <Select
            onValueChange={(v) => {
              if (v) onSelectCase(v as string);
            }}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a sample case…" />
            </SelectTrigger>
            <SelectContent>
              {SAMPLE_CASES.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="note">Intake note</Label>
          <Textarea
            id="note"
            value={note}
            onChange={(e) => onNoteChange(e.target.value)}
            placeholder="Type or paste a free-text patient intake note…"
            className="min-h-40 resize-y"
          />
        </div>

        <Button
          onClick={onSubmit}
          disabled={loading || !note.trim()}
          className="w-full"
        >
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Send className="size-4" />
          )}
          {loading ? "Summarizing…" : "Submit intake"}
        </Button>
      </CardContent>
    </Card>
  );
}
