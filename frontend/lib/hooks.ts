"use client";

import useSWRMutation from "swr/mutation";
import { enroll as enrollApi, synthesize as synthesizeApi } from "./api";
import { usePolyvoxStore } from "./store";

export function useEnroll() {
  const setEnrolled = usePolyvoxStore((s) => s.setEnrolled);

  const { trigger, isMutating, error } = useSWRMutation(
    "enroll",
    async (_key, { arg }: { arg: { userId: string; audioBlob: Blob } }) => {
      const result = await enrollApi(arg.userId, arg.audioBlob);
      setEnrolled(true);
      return result;
    }
  );

  return {
    enroll: trigger,
    isMutating,
    error,
  };
}

export function useSynthesize() {
  const { trigger, data, isMutating, error } = useSWRMutation(
    "synthesize",
    async (_key, { arg }: { arg: { userId: string; text: string; voiceId: string } }) => {
      return synthesizeApi(arg.userId, arg.text, arg.voiceId);
    }
  );

  return {
    synthesize: trigger,
    data,
    isMutating,
    error,
  };
}
