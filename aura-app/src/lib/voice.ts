import { startVad, type Vad } from "./vad";
import { stopMic } from "./audio";
type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult:
    | ((event: {
        results: ArrayLike<
          ArrayLike<{ transcript: string }> & { isFinal: boolean }
        >;
        resultIndex: number;
      }) => void)
    | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};
export async function listen(
  cloud: boolean,
  onText: (text: string) => void,
  onLevel: (n: number) => void,
  onError: (s: string) => void,
): Promise<() => void> {
  let stopped = false;
  let vad: Vad | undefined;
  let recognition: Recognition | undefined;
  let armedUntil = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const transcript = (text: string) => {
    const match = /\bhey[ ,]+aura\b[,.!]?\s*/i.exec(text);
    if (match) {
      armedUntil = Date.now() + 15000;
      const rest = text.slice(match.index + match[0].length).trim();
      if (rest) {
        onText(rest);
        armedUntil = 0;
      } else onError("Listening — say your message.");
      return;
    }
    if (Date.now() < armedUntil) {
      onText(text);
      armedUntil = 0;
      return;
    }
    if (
      /\b(?:i need help|i need support|i feel overwhelmed|i feel panicked|i feel unsafe|i can.t cope)\b/i.test(
        text,
      )
    )
      onText(text);
  };
  try {
    if (cloud) {
      vad = await startVad({
        onStart: () => speechSynthesis.cancel(),
        onLevel,
        onError,
        onEnd: async (blob) => {
          if (stopped) return;
          try {
            const res = await fetch("/api/stt", {
              method: "POST",
              headers: { "Content-Type": blob.type },
              body: blob,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            if (!stopped) transcript(data.text || "");
          } catch {
            onError("Transcription failed. You can type your message.");
          }
        },
      });
      if (!vad.live()) throw new Error("Microphone unavailable");
    } else {
      const browser = window as SpeechWindow;
      const Ctor = browser.SpeechRecognition || browser.webkitSpeechRecognition;
      if (!Ctor)
        throw new Error(
          "Voice recognition needs Chrome or Edge. You can still type here.",
        );
      recognition = new Ctor();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = "en-US";
      recognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            speechSynthesis.cancel();
            transcript(event.results[i][0].transcript);
          }
        }
      };
      recognition.onerror = (event) => {
        onError("Microphone: " + event.error);
        if (
          ["not-allowed", "service-not-allowed", "audio-capture"].includes(
            event.error,
          )
        ) {
          stopped = true;
          recognition?.abort();
        }
      };
      recognition.onend = () => {
        if (!stopped)
          timer = setTimeout(() => {
            try {
              recognition?.start();
            } catch {
              onError("Click microphone off, then on to reconnect.");
            }
          }, 600);
      };
      recognition.start();
    }
  } catch (error) {
    vad?.stop();
    stopMic();
    throw error;
  }
  return () => {
    stopped = true;
    clearTimeout(timer);
    recognition?.abort();
    vad?.stop();
    stopMic();
    onLevel(0);
  };
}
let currentAudio: HTMLAudioElement | undefined;
let speechEpoch = 0;
let finishSpeech = () => {};
export function silence() {
  speechEpoch++;
  speechSynthesis.cancel();
  currentAudio?.pause();
  currentAudio = undefined;
  finishSpeech();
}
export async function speak(
  text: string,
  cloud: boolean,
  voiceURI = "",
  rate = 0.97,
) {
  silence();
  const epoch = speechEpoch;
  if (cloud) {
    try {
      const response = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) throw new Error();
      const url = URL.createObjectURL(await response.blob());
      if (epoch !== speechEpoch) {
        URL.revokeObjectURL(url);
        return;
      }
      const audio = new Audio(url);
      currentAudio = audio;
      await new Promise<void>((resolve) => {
        let finished = false;
        const done = () => {
          if (finished) return;
          finished = true;
          URL.revokeObjectURL(url);
          if (currentAudio === audio) currentAudio = undefined;
          finishSpeech = () => {};
          resolve();
        };
        finishSpeech = done;
        audio.onended = done;
        audio.onerror = done;
        void audio.play().catch(done);
      });
      return;
    } catch {
      /* browser speech fallback */
    }
  }
  if (epoch !== speechEpoch) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = Math.min(1.2, Math.max(0.8, rate));
  if (voiceURI) {
    utterance.voice =
      speechSynthesis
        .getVoices()
        .find((voice) => voice.voiceURI === voiceURI) ?? null;
  }
  await new Promise<void>((resolve) => {
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      finishSpeech = () => {};
      resolve();
    };
    finishSpeech = done;
    utterance.onend = done;
    utterance.onerror = done;
    speechSynthesis.speak(utterance);
  });
}
