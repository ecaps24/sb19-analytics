import { FORMAT_THRESHOLDS } from '../constants';

export function formatNumber(num: number): string {
  if (num >= FORMAT_THRESHOLDS.BILLION) {
    return (num / FORMAT_THRESHOLDS.BILLION).toFixed(2) + 'B';
  }
  if (num >= FORMAT_THRESHOLDS.MILLION) {
    return (num / FORMAT_THRESHOLDS.MILLION).toFixed(1) + 'M';
  }
  if (num >= FORMAT_THRESHOLDS.THOUSAND) {
    return (num / FORMAT_THRESHOLDS.THOUSAND).toFixed(0) + 'K';
  }
  return num.toString();
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '';

  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export function formatDateTime(dateStr: string): string {
  if (!dateStr) return '';

  try {
    const date = new Date(dateStr);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export function formatChange(change: number, includeSign = true): string {
  const formatted = formatNumber(Math.abs(change));
  if (!includeSign) return formatted;
  return change >= 0 ? `+${formatted}` : `-${formatted}`;
}

export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

// Custom hook for formatters
export function useFormatters() {
  return {
    formatNumber,
    formatDate,
    formatDateTime,
    formatChange,
    formatPercent,
  };
}
