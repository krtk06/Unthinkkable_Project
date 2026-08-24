import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface GridPatternCardProps {
  children: React.ReactNode;
  className?: string;
  patternClassName?: string;
  gradientClassName?: string;
}

export function GridPatternCard({
  children,
  className,
  patternClassName,
  gradientClassName,
}: GridPatternCardProps) {
  return (
    <motion.div
      className={cn(
        "border w-full rounded-md overflow-hidden",
        "dark:border-zinc-900 border-border",
        "dark:bg-zinc-950 bg-[#0e1116]",
        "p-1",
        className
      )}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      whileHover={{ y: -2 }}
    >
      <div
        className={cn(
          "size-full bg-repeat bg-[url(/svg/grid-ellipsis.svg)] bg-[length:25px_25px]",
          patternClassName
        )}
      >
        <div
          className={cn(
            "size-full bg-gradient-to-tr",
            "from-zinc-950 via-zinc-950/70 to-zinc-950",
            gradientClassName
          )}
        >
          {children}
        </div>
      </div>
    </motion.div>
  );
}

export function GridPatternCardBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("text-start p-4 md:p-6", className)} {...props} />
  );
}
