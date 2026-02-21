import { EnrollSection } from "@/components/EnrollSection";
import { PracticeSection } from "@/components/PracticeSection";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center bg-background p-6">
      <main className="w-full max-w-2xl space-y-8">
        <header className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">
            Polyvox - SA Accent Trainer
          </h1>
          <p className="mt-2 text-muted-foreground">
            Record your voice, then generate South African-accented speech
          </p>
        </header>

        <EnrollSection />
        <PracticeSection />
      </main>
    </div>
  );
}
