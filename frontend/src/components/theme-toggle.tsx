"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { IconTooltip } from "@/components/ui/tooltip";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    // Label stays "Toggle theme" rather than naming the destination theme
    // ("Switch to light"): before mount, resolvedTheme is undefined, so any
    // destination-based label would render wrong on first paint and then
    // change — the same hydration reason the icon itself is gated on mounted.
    <IconTooltip label="Toggle theme">
      <Button
        variant="ghost"
        size="icon"
        aria-label="Toggle theme"
        onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      >
        {mounted && resolvedTheme === "dark" ? <Sun /> : <Moon />}
      </Button>
    </IconTooltip>
  );
}
