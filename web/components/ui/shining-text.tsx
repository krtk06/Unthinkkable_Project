"use client";
import { motion } from "framer-motion";

interface ShiningTextProps {
  text: string;
  className?: string;
}

export function ShiningText({ text, className }: ShiningTextProps) {
  return (
    <motion.span
      className={className}
      style={{
        backgroundImage:
          "linear-gradient(90deg, #9a9890 0%, #9a9890 40%, #ffffff 50%, #9a9890 60%, #9a9890 100%)",
        backgroundSize: "200% 100%",
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        WebkitTextFillColor: "transparent",
        color: "transparent",
        display: "inline-block",
      }}
      initial={{ backgroundPosition: "100% 0%" }}
      animate={{ backgroundPosition: ["100% 0%", "-100% 0%"] }}
      transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
    >
      {text}
    </motion.span>
  );
}
