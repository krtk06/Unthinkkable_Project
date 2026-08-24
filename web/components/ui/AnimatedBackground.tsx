import { cn } from "@/lib/utils";

/**
 * Full-viewport animated dark background with drifting gradient glows.
 */
export function AnimatedBackground({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#0b0d10]",
        className
      )}
    >
      <div className="absolute inset-0 animate-gradient bg-[radial-gradient(circle_700px_at_20%_10%,#16a34a66,transparent)]" />
      <div className="absolute inset-0 animate-gradient-delayed bg-[radial-gradient(circle_600px_at_85%_85%,#7c3aed66,transparent)]" />
      <div className="absolute inset-0 animate-gradient-delayed-2 bg-[radial-gradient(circle_600px_at_90%_10%,#0ea5e955,transparent)]" />
    </div>
  );
}