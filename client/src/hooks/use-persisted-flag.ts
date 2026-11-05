import { useCallback, useState } from "react";
import { readStoredFlag, writeStoredFlag } from "@/lib/stored-flag";

function browserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    // Accessing localStorage itself can throw (blocked site data).
    return null;
  }
}

/** A boolean UI preference remembered per viewer in localStorage (works without it). */
export function usePersistedFlag(key: string, fallback: boolean): [boolean, (next: boolean) => void] {
  const [value, setValue] = useState(() => readStoredFlag(browserStorage(), key, fallback));

  const update = useCallback(
    (next: boolean) => {
      setValue(next);
      writeStoredFlag(browserStorage(), key, next);
    },
    [key],
  );

  return [value, update];
}
