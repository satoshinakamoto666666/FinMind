export interface LocaleFormatOptions {
  locale?: string;
  currency?: string;
  minimumFractionDigits?: number;
  maximumFractionDigits?: number;
}

export function formatLocalizedCurrency(
  amount: number,
  { locale = "en-US", currency = "USD" }: LocaleFormatOptions = {}
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
  }).format(amount);
}

export function formatLocalizedNumber(
  value: number,
  { locale = "en-US", minimumFractionDigits = 0, maximumFractionDigits = 2 }: LocaleFormatOptions = {}
): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(value);
}

export function formatLocalizedDate(
  isoDate: string | Date,
  locale: string = "en-US"
): string {
  const d = typeof isoDate === "string" ? new Date(isoDate) : isoDate;
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}
