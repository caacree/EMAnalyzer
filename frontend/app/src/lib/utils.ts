import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";


export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export const formatNumber = (number: number) => {
  if (number < 1000) {
    return number.toString(); // Show numbers less than 1000 normally
  }
  if (number < 10000) {
    return `${(number / 1000).toFixed(1)}k`; // Divide by 1000 and show 1 decimal place followed by "k"
  }
  if (number < 1000000) {
    return `${Math.floor(number / 1000)}k`; // Divide by 1000 and show "k"
  }
  if (number < 1000000000) {
    return `${(number / 1000000).toFixed(1)}M`; // Divide by 1 million and show 1 decimal place followed by "M"
  }
  return `${Math.floor(number / 1000000)}M`; // Divide by 1 million and show "M"
};
