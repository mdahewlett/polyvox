const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function enroll(userId: string, audioBlob: Blob): Promise<{ status: string; user_id: string }> {
  const formData = new FormData();
  formData.append("user_id", userId);

  const ext = audioBlob.type.includes("wav") ? ".wav" : audioBlob.type.includes("mp3") ? ".mp3" : ".webm";
  const file = new File([audioBlob], `voice${ext}`, { type: audioBlob.type });
  formData.append("audio", file);

  const res = await fetch(`${API_BASE}/enroll`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Enroll failed");
  }

  return res.json();
}

export async function synthesize(
  userId: string,
  text: string
): Promise<{ status: string; audio_url: string; original_audio_url: string }> {
  const formData = new FormData();
  formData.append("user_id", userId);
  formData.append("text", text);

  const res = await fetch(`${API_BASE}/synthesize`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Synthesize failed");
  }

  return res.json();
}

export function getAudioUrl(audioPath: string): string {
  if (audioPath.startsWith("http")) return audioPath;
  const path = audioPath.startsWith("/") ? audioPath : `/${audioPath}`;
  return `${API_BASE}${path}`;
}
