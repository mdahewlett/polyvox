"use client";

import { useRef, useState } from "react";
import { Mic, Upload, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { usePolyvoxStore } from "@/lib/store";
import { useEnroll } from "@/lib/hooks";

export function EnrollSection() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const getOrCreateUserId = usePolyvoxStore((s) => s.getOrCreateUserId);
  const isEnrolled = usePolyvoxStore((s) => s.isEnrolled);
  const { enroll, isMutating } = useEnroll();

  const [isRecording, setIsRecording] = useState(false);

  const handleRecord = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        setIsRecording(false);
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const userId = getOrCreateUserId();

        try {
          await enroll({ userId, audioBlob: blob });
          toast.success("Voice enrolled successfully!");
        } catch (err) {
          toast.error(err instanceof Error ? err.message : "Enroll failed");
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      toast.error("Could not access microphone");
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const userId = getOrCreateUserId();
    const blob = await file.arrayBuffer().then((b) => new Blob([b], { type: file.type }));

    try {
      await enroll({ userId, audioBlob: blob });
      toast.success("Voice enrolled successfully!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Enroll failed");
    }

    e.target.value = "";
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Enroll Your Voice</CardTitle>
        <div className="flex items-center gap-2">
          {isEnrolled && (
            <Badge variant="secondary" className="gap-1">
              <Check className="size-3" />
              Voice enrolled
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          <Button
            variant={isRecording ? "destructive" : "default"}
            onClick={handleRecord}
            disabled={isMutating}
          >
            <Mic className="size-4" />
            {isRecording ? "Stop Recording" : "Record Voice Sample"}
          </Button>
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={isMutating}
          >
            <Upload className="size-4" />
            Upload File
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".wav,.mp3,.m4a,.webm,.ogg"
            className="hidden"
            onChange={handleUpload}
          />
        </div>
      </CardContent>
    </Card>
  );
}
