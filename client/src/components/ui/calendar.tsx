"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker, type CaptionProps, useNavigation, useDayPicker } from "react-day-picker";
import { format } from "date-fns";

import { cn } from "./utils";
import { buttonVariants } from "./button";

/** Custom caption — renders clean Month + Year selects, no duplicate static labels */
function CalendarCaption({ displayMonth }: CaptionProps) {
  const { goToMonth, nextMonth, previousMonth } = useNavigation();
  const { fromYear, toYear } = useDayPicker();
  const currentYear = new Date().getFullYear();
  const startYear = fromYear ?? currentYear - 5;
  const endYear = toYear ?? currentYear + 3;

  const years = Array.from({ length: endYear - startYear + 1 }, (_, i) => startYear + i);
  const months = Array.from({ length: 12 }, (_, i) => i);

  const handleMonthChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const d = new Date(displayMonth);
    d.setMonth(Number(e.target.value));
    goToMonth(d);
  };

  const handleYearChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const d = new Date(displayMonth);
    d.setFullYear(Number(e.target.value));
    goToMonth(d);
  };

  const selectCls = [
    "h-7 appearance-none rounded border border-border bg-background",
    "px-2 py-0.5 text-xs font-semibold text-foreground",
    "hover:bg-muted focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer",
  ].join(" ");

  return (
    <div className="flex items-center justify-between w-full px-1">
      <button
        type="button"
        onClick={() => previousMonth && goToMonth(previousMonth)}
        disabled={!previousMonth}
        className={cn(
          buttonVariants({ variant: "outline" }),
          "size-7 bg-transparent p-0 opacity-50 hover:opacity-100 disabled:pointer-events-none",
        )}
      >
        <ChevronLeft className="size-4" />
      </button>

      <div className="flex items-center gap-1.5">
        <select
          value={displayMonth.getMonth()}
          onChange={handleMonthChange}
          className={selectCls}
        >
          {months.map((m) => (
            <option key={m} value={m}>
              {format(new Date(2000, m, 1), "MMMM")}
            </option>
          ))}
        </select>

        <select
          value={displayMonth.getFullYear()}
          onChange={handleYearChange}
          className={selectCls}
        >
          {years.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      <button
        type="button"
        onClick={() => nextMonth && goToMonth(nextMonth)}
        disabled={!nextMonth}
        className={cn(
          buttonVariants({ variant: "outline" }),
          "size-7 bg-transparent p-0 opacity-50 hover:opacity-100 disabled:pointer-events-none",
        )}
      >
        <ChevronRight className="size-4" />
      </button>
    </div>
  );
}

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: React.ComponentProps<typeof DayPicker>) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-3", className)}
      classNames={{
        months: "flex flex-col sm:flex-row gap-4",
        month: "flex flex-col gap-4",
        caption: "flex justify-center pt-1 relative items-center w-full",
        caption_label: "text-sm font-medium",
        nav: "flex items-center gap-1",
        nav_button: cn(
          buttonVariants({ variant: "outline" }),
          "size-7 bg-transparent p-0 opacity-50 hover:opacity-100",
        ),
        nav_button_previous: "absolute left-1",
        nav_button_next: "absolute right-1",
        table: "w-full border-collapse space-x-1",
        head_row: "flex",
        head_cell: "text-muted-foreground rounded-md w-8 font-normal text-[0.8rem]",
        row: "flex w-full mt-2",
        cell: cn(
          "relative p-0 text-center text-sm focus-within:relative focus-within:z-20 [&:has([aria-selected])]:bg-accent [&:has([aria-selected].day-range-end)]:rounded-r-md",
          props.mode === "range"
            ? "[&:has(>.day-range-end)]:rounded-r-md [&:has(>.day-range-start)]:rounded-l-md first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md"
            : "[&:has([aria-selected])]:rounded-md",
        ),
        day: cn(
          buttonVariants({ variant: "ghost" }),
          "size-8 p-0 font-normal aria-selected:opacity-100",
        ),
        day_range_start:
          "day-range-start aria-selected:bg-primary aria-selected:text-primary-foreground",
        day_range_end:
          "day-range-end aria-selected:bg-primary aria-selected:text-primary-foreground",
        day_selected:
          "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
        day_today: "bg-accent text-accent-foreground",
        day_outside: "day-outside text-muted-foreground aria-selected:text-muted-foreground",
        day_disabled: "text-muted-foreground opacity-50",
        day_range_middle: "aria-selected:bg-primary/10 aria-selected:text-primary",
        day_hidden: "invisible",
        ...classNames,
      }}
      components={{ Caption: CalendarCaption }}
      {...props}
    />
  );
}

export { Calendar };