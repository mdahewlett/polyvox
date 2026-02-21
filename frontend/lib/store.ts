import { create } from "zustand";
import { persist } from "zustand/middleware";

function generateUserId(): string {
  return crypto.randomUUID();
}

export interface PolyvoxStore {
  userId: string;
  isEnrolled: boolean;
  setEnrolled: (enrolled: boolean) => void;
  getOrCreateUserId: () => string;
}

export const usePolyvoxStore = create<PolyvoxStore>()(
  persist(
    (set, get) => ({
      userId: "",
      isEnrolled: false,

      setEnrolled: (enrolled: boolean) => set({ isEnrolled: enrolled }),

      getOrCreateUserId: () => {
        const current = get().userId;
        if (current) return current;

        const newId = generateUserId();
        set({ userId: newId });
        return newId;
      },
    }),
    {
      name: "polyvox-store",
      partialize: (state) => ({ userId: state.userId }),
    }
  )
);
