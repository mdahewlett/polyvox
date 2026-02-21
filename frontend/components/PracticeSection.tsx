"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { usePolyvoxStore } from "@/lib/store";
import { useSynthesize } from "@/lib/hooks";
import { getAudioUrl, getVoices, type Voice } from "@/lib/api";

export function PracticeSection() {
  const [text, setText] = useState("");
  const [voiceId, setVoiceId] = useState("Ayanda");

  const getOrCreateUserId = usePolyvoxStore((s) => s.getOrCreateUserId);
  const isEnrolled = usePolyvoxStore((s) => s.isEnrolled);
  const { synthesize, data, isMutating } = useSynthesize();
  const { data: voicesData } = useSWR("voices", () => getVoices());

  const voices: Voice[] = voicesData?.voices ?? [];

  const handleGenerate = async () => {
    const userId = getOrCreateUserId();
    try {
      await synthesize({ userId, text, voiceId });
      toast.success("Audio generated!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Synthesis failed");
    }
  };

  const canGenerate = text.trim().length > 0 && !isMutating;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Practice SA Accent</CardTitle>
        {!isEnrolled && (
          <CardDescription>
            Using default voice. Enroll to hear text in your own voice.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="space-y-2">
          <Label>Base voice</Label>
          <Select
            value={voiceId}
            onValueChange={setVoiceId}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select voice" />
            </SelectTrigger>
            <SelectContent>
              {voices.map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  {v.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="practice-text">Enter text to speak</Label>
          <Textarea
            id="practice-text"
            placeholder="Hello, how are you today?"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
          />
        </div>

        <Button
          onClick={handleGenerate}
          disabled={!canGenerate}
        >
          {isMutating ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Generating...
            </>
          ) : (
            "Generate SA Accent"
          )}
        </Button>

        {data?.audio_url && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Listen</Label>
              <audio
                controls
                src={getAudioUrl(data.audio_url)}
                className="w-full"
              />
            </div>
            <div className="space-y-2">
              <Label>Original</Label>
              <audio
                controls
                src={getAudioUrl(data.original_audio_url)}
                className="w-full"
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
