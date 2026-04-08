"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type SliderProps = {
  className?: string
  value?: number[]
  defaultValue?: number[]
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  orientation?: "horizontal" | "vertical"
  style?: React.CSSProperties
  "aria-label"?: string
  onValueChange?: (value: number[]) => void
}

function Slider({
  className,
  value,
  defaultValue,
  min = 0,
  max = 100,
  step = 1,
  disabled,
  orientation = "horizontal",
  style,
  onValueChange,
  ...props
}: SliderProps) {
  const current = value?.[0] ?? defaultValue?.[0] ?? min
  const range = max - min
  const pct = range > 0 ? ((current - min) / range) * 100 : 0
  const isVertical = orientation === "vertical"

  return (
    <div
      data-slot="slider"
      data-orientation={orientation}
      style={style}
      className={cn(
        "relative flex touch-none select-none",
        isVertical
          ? "h-full w-3 flex-col items-center justify-center"
          : "w-full items-center",
        disabled && "opacity-50",
        className,
      )}
    >
      <div
        aria-hidden="true"
        className={cn(
          "relative overflow-hidden rounded-full bg-muted",
          isVertical ? "h-full w-1" : "h-1 w-full",
        )}
      >
        <div
          className={cn(
            "absolute bg-primary",
            isVertical ? "inset-x-0 bottom-0" : "inset-y-0 left-0",
          )}
          style={isVertical ? { height: `${pct}%` } : { width: `${pct}%` }}
        />
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={current}
        disabled={disabled}
        onChange={(e) => onValueChange?.([Number(e.target.value)])}
        aria-label={props["aria-label"]}
        aria-orientation={orientation}
        style={
          isVertical
            ? {
                WebkitAppearance: "slider-vertical",
                writingMode: "vertical-lr" as React.CSSProperties["writingMode"],
                direction: "rtl",
              }
            : undefined
        }
        className={cn(
          "absolute inset-0 cursor-pointer appearance-none bg-transparent",
          isVertical ? "h-full w-full" : "h-full w-full",
          "[&::-webkit-slider-runnable-track]:bg-transparent",
          "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:size-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border [&::-webkit-slider-thumb]:border-ring [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:transition-[box-shadow] [&::-webkit-slider-thumb]:hover:ring-3 [&::-webkit-slider-thumb]:hover:ring-ring/50 [&::-webkit-slider-thumb]:focus-visible:ring-3 [&::-webkit-slider-thumb]:focus-visible:ring-ring/50",
          !isVertical &&
            "[&::-webkit-slider-runnable-track]:h-1 [&::-webkit-slider-thumb]:-mt-1",
          "[&::-moz-range-track]:h-1 [&::-moz-range-track]:bg-transparent [&::-moz-range-track]:border-0",
          "[&::-moz-range-thumb]:size-3 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border [&::-moz-range-thumb]:border-ring [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:transition-[box-shadow] [&::-moz-range-thumb]:hover:ring-3 [&::-moz-range-thumb]:hover:ring-ring/50",
          "focus:outline-none disabled:pointer-events-none",
        )}
      />
    </div>
  )
}

export { Slider }
