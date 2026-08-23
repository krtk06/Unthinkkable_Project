"use client";

import { motion, type Variants } from "framer-motion";
import { type ReactNode } from "react";
import { usePrefersReducedMotion } from "@/lib/hooks";

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  animate?: boolean;
}

export default function GlassCard({
  children,
  className = "",
  hover = false,
  animate = true,
}: GlassCardProps) {
  const prefersReduced = usePrefersReducedMotion();
  const shouldAnimate = animate && !prefersReduced;

  return (
    <motion.div
      className={`glass ${hover ? "transition-all duration-200 hover:border-border-hover" : ""} ${className}`}
      variants={shouldAnimate ? cardVariants : undefined}
      initial={shouldAnimate ? "hidden" : undefined}
      animate={shouldAnimate ? "visible" : undefined}
    >
      {children}
    </motion.div>
  );
}
