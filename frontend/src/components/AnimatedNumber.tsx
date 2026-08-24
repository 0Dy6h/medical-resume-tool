import { useEffect, useRef, useState } from "react";

/**
 * Easing function: cubic ease-out.
 * Pure function — exported for testing.
 */
export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Linear interpolation between two numbers.
 * Pure function — exported for testing.
 */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Format a number with locale, decimals, and optional prefix/suffix.
 * Pure function — exported for testing.
 */
export function formatNumber(value: number, decimals: number, prefix?: string, suffix?: string): string {
  const formatted = value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `${prefix ?? ""}${formatted}${suffix ?? ""}`;
}

type AnimatedNumberProps = {
  value: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
};

export function AnimatedNumber({ value, duration = 400, prefix, suffix, decimals = 0 }: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const startValueRef = useRef<number>(value);
  const targetValueRef = useRef<number>(value);

  useEffect(() => {
    const reducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reducedMotion || duration <= 0) {
      setDisplayValue(value);
      return;
    }

    // Kick off a new animation from the current display value to the new target.
    startValueRef.current = displayValue;
    targetValueRef.current = value;
    startTimeRef.current = null;

    function frame(now: number) {
      if (startTimeRef.current === null) {
        startTimeRef.current = now;
      }
      const elapsed = now - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutCubic(progress);
      const current = lerp(startValueRef.current, targetValueRef.current, eased);
      setDisplayValue(current);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(frame);
      } else {
        rafRef.current = null;
      }
    }

    rafRef.current = requestAnimationFrame(frame);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
    // We intentionally only re-run when `value` or `duration` changes.
    // `displayValue` is used as the starting point but not as a dependency
    // to avoid infinite loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);

  return <>{formatNumber(displayValue, decimals, prefix, suffix)}</>;
}
