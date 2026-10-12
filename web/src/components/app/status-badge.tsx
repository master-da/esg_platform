import { cn } from "@/lib/utils";

type Tone = "green" | "amber" | "red" | "blue" | "gray" | "violet";

const TONE: Record<Tone, string> = {
  green: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  blue: "bg-sky-50 text-sky-800 ring-sky-200",
  gray: "bg-muted text-muted-foreground ring-border",
  violet: "bg-violet-50 text-violet-800 ring-violet-200",
};

const KNOWN: Record<string, { label: string; tone: Tone }> = {
  // file statuses (PRD 5.1)
  READY_TO_CATEGORIZE: { label: "Ready to categorize", tone: "gray" },
  PRELIMINARY: { label: "Preliminary", tone: "amber" },
  CALCULATED: { label: "Calculated", tone: "green" },
  NEED_ATTENTION: { label: "Need attention", tone: "red" },
  CONFIRMED: { label: "✓ Confirmed", tone: "green" },
  AWAITING_CONFIRMATION: { label: "Awaiting confirmation", tone: "amber" },
  // project stages (PRD 3)
  DRAFT: { label: "DRAFT", tone: "gray" },
  DATA_COLLECTION: { label: "DATA_COLLECTION", tone: "blue" },
  REVIEW: { label: "REVIEW", tone: "violet" },
  APPROVED: { label: "APPROVED", tone: "green" },
  LOCKED: { label: "LOCKED", tone: "gray" },
  // categorization
  NEEDS: { label: "Needs categorization", tone: "gray" },
  SUGGESTED: { label: "Suggested", tone: "amber" },
  ACCEPTED: { label: "Accepted", tone: "green" },
  // review / verification
  AI_EXTRACTED: { label: "AI_EXTRACTED", tone: "violet" },
  USER_VERIFIED: { label: "USER_VERIFIED", tone: "green" },
  pending_review: { label: "Pending review", tone: "amber" },
  // compliance
  PASS: { label: "PASS", tone: "green" },
  WARNING: { label: "WARNING", tone: "amber" },
  FAIL: { label: "FAIL", tone: "red" },
  VERIFIED: { label: "Verified", tone: "green" },
  NEEDS_REVIEW: { label: "NEEDS_REVIEW", tone: "amber" },
  UNKNOWN: { label: "UNKNOWN", tone: "red" },
  // people
  active: { label: "Active", tone: "green" },
  invited: { label: "Invited", tone: "amber" },
  disabled: { label: "Disabled", tone: "gray" },
  operating: { label: "Operating", tone: "green" },
  under_construction: { label: "Under construction", tone: "blue" },
  idle: { label: "Idle", tone: "amber" },
  closed: { label: "Closed", tone: "gray" },
};

export function StatusBadge({ status, label, tone }: { status: string; label?: string; tone?: Tone }) {
  const known = KNOWN[status];
  const t = tone ?? known?.tone ?? "gray";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONE[t],
      )}
    >
      {label ?? known?.label ?? status}
    </span>
  );
}
