"use client";

import { useEffect, useState } from "react";

import { type Locale } from "@/lib/i18n";

type LocalizedTimestampProps = {
  locale: Locale;
  value: string | null;
  emptyLabel?: string;
  dateStyle?: Intl.DateTimeFormatOptions["dateStyle"];
  timeStyle?: Intl.DateTimeFormatOptions["timeStyle"];
  className?: string;
};

function getLocaleTag(locale: Locale): string {
  return locale === "ru" ? "ru-RU" : "en-US";
}

function formatTimestamp(
  locale: Locale,
  value: string,
  dateStyle: Intl.DateTimeFormatOptions["dateStyle"],
  timeStyle: Intl.DateTimeFormatOptions["timeStyle"]
): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat(getLocaleTag(locale), {
    dateStyle,
    timeStyle
  }).format(date);
}

export function LocalizedTimestamp({
  locale,
  value,
  emptyLabel = "-",
  dateStyle = "medium",
  timeStyle = "medium",
  className
}: LocalizedTimestampProps) {
  const [formattedValue, setFormattedValue] = useState<string | null>(null);

  useEffect(() => {
    if (!value) {
      setFormattedValue(null);
      return;
    }

    setFormattedValue(formatTimestamp(locale, value, dateStyle, timeStyle));
  }, [dateStyle, locale, timeStyle, value]);

  if (!value) {
    return <span className={className}>{emptyLabel}</span>;
  }

  return (
    <time className={className} dateTime={value} suppressHydrationWarning title={value}>
      {formattedValue ?? emptyLabel}
    </time>
  );
}
