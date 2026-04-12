import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with proper precedence.
 * @param inputs - Class names or conditional class expressions
 * @returns Merged class string
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format money in KES from cents to display string.
 * @param cents - Amount in KES cents (integer)
 * @returns Formatted string like "KES 1,234.56"
 */
export function formatKES(cents: number): string {
  const amount = cents / 100;
  return `KES ${amount.toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Format a date to Africa/Nairobi timezone.
 * @param date - ISO date string or Date object
 * @returns Formatted date string
 */
export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-KE", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(date));
}

/**
 * Format a datetime to Africa/Nairobi timezone.
 * @param date - ISO date string or Date object
 * @returns Formatted datetime string
 */
export function formatDateTime(date: string | Date): string {
  return new Intl.DateTimeFormat("en-KE", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

/**
 * Generate a UUID v4.
 * @returns UUID string
 */
export function generateId(): string {
  return crypto.randomUUID();
}
