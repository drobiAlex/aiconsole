import { useAudioStore } from './useAudioStore';

export function startCheckingForSilence(stream: MediaStream) {
  let audioContext: AudioContext;

  try {
    //@ts-expect-error - Attempt to use standard AudioContext; fallback to webkitAudioContext for older browsers
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  } catch (error) {
    console.error('AudioContext is not supported in this browser.', error);
    return;
  }

  const analyser = audioContext.createAnalyser();
  const microphone = audioContext.createMediaStreamSource(stream);
  microphone.connect(analyser);
  const dataArray = new Uint8Array(analyser.frequencyBinCount);
  let silenceStart = performance.now();
  const silenceThreshold = 5000; // 5 seconds of silence threshold

  const cleanUp = () => {
    microphone.disconnect();
    audioContext.close();
  };

  const checkSilence = () => {
    if (!useAudioStore.getState().isRecordingVoice) {
      cleanUp();
      return;
    }

    analyser.getByteTimeDomainData(dataArray);
    const average = calculateAverage(dataArray);

    if (isSilent(average)) {
      if (performance.now() - silenceStart > silenceThreshold) {
        useAudioStore.getState().stopRecording(); // Automatically stop recording
        cleanUp();
        return;
      }
    } else {
      silenceStart = performance.now();
    }

    requestAnimationFrame(checkSilence);
  };

  checkSilence();
}

function calculateAverage(dataArray: Uint8Array): number {
  const sum = dataArray.reduce((acc, val) => acc + Math.abs(val - 128), 0);
  return sum / dataArray.length;
}

function isSilent(average: number): boolean {
  return average < 1;
}
