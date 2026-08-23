import { type ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}

export default function GlassCard({ children, className = "", hover = false }: GlassCardProps) {
  return (
    <div
      className={`glass ${hover ? "transition-all duration-200 hover:border-border-hover" : ""} ${className}`}
    >
      {children}
    </div>
  );
}
