import { create } from 'zustand';
import { AudioAPI } from '@/api/api/AudioAPI';
import { detectVoice } from './detectVoice';
import { useToastsStore } from '@/store/common/useToastsStore';
import { startCheckingForSilence } from './startCheckingForSilence';

interface SoundPromise {
  promise: Promise<Howl>;
  isFinished: boolean;
}

interface AudioState {
  isVoiceModeEnabled: boolean;

  soundsToPlayQueue: SoundPromise[];
  queuedTextSoFar: string;

  isPlaying: boolean;
  numLoading: number;

  readText: (text: string, canBeContinued: boolean) => Promise<void>;
  stopReading: () => void;
  startRecording: () => void;
  stopRecording: () => void;
  recordedVoice?: Blob;
  isRecording: boolean;
  isPlayingPaused: boolean;
  isRecordingPaused: boolean;
  mediaRecorder?: MediaRecorder;
}

async function enqueueText(text: string) {
  console.log('Enqueuing text:', text);

  const newSoundPromise: SoundPromise = {
    promise: AudioAPI.textToSpeech(text),
    isFinished: false,
  };

  useAudioStore.setState((state: AudioState) => ({ numLoading: state.numLoading + 1 }));

  const after = () => {
    useAudioStore.setState((state: AudioState) => ({ numLoading: state.numLoading - 1 }));
    newSoundPromise.isFinished = true;
    processSoundsToPlayQueue();
  };

  newSoundPromise.promise.then(after, after);
  useAudioStore.setState((state: AudioState) => ({
    soundsToPlayQueue: [...state.soundsToPlayQueue, newSoundPromise],
  }));

  if (!useAudioStore.getState().isPlaying) {
    processSoundsToPlayQueue();
  }
}

async function processSoundsToPlayQueue() {
  const { soundsToPlayQueue: soundQueue, isPlaying, numLoading } = useAudioStore.getState();
  console.log('Processing queue', soundQueue.length, isPlaying, numLoading);
  if (soundQueue.length === 0 || !soundQueue[0].isFinished || isPlaying) return;
  const sound: Howl = await soundQueue[0].promise;
  setTimeout(() => {
    sound.once('end', () => {
      useAudioStore.setState({ isPlaying: false });
      useAudioStore.setState((state) => ({ soundsToPlayQueue: state.soundsToPlayQueue.slice(1) }));

      //if queue is empty then we are done
      if (useAudioStore.getState().soundsToPlayQueue.length === 0) {
        const startRecording = useAudioStore.getState().startRecording;
        if (useAudioStore.getState().isVoiceModeEnabled && startRecording) {
          startRecording();
        }
      }

      console.log('Sound finished:', sound, soundQueue[0].promise, soundQueue[0].isFinished);
      processSoundsToPlayQueue(); // Process the next item in the queue
    });
    sound.play();
    console.log('Playing sound:', sound);
  }, 100); // delay between sounds
  useAudioStore.setState({ isPlaying: true });
}

export const useAudioStore = create<AudioState>((set, get) => ({
  soundsToPlayQueue: [],
  isVoiceModeEnabled: false,
  isPlaying: false,
  isRecordingPaused: false,
  numLoading: 0,
  queuedTextSoFar: '',
  audioTrackConstraints: undefined,
  mediaRecorderOptions: undefined,

  isRecording: false,
  isPlayingPaused: false,
  mediaRecorder: undefined,
  recordedVoice: undefined,

  readText: async (text: string, canBeContinued: boolean) => {
    set({ isVoiceModeEnabled: true });

    if (text === '') {
      set({ queuedTextSoFar: '' });
      return;
    }

    const { queuedTextSoFar } = get();
    if (text.startsWith(queuedTextSoFar)) {
      const remainingText = text.slice(queuedTextSoFar.length);
      if (canBeContinued) {
        const paragraphs = remainingText.split(/\n\n+/);
        if (paragraphs.length > 1) {
          const fullParagraphs = paragraphs.slice(0, paragraphs.length - 1).join('\n\n');
          const remainingTextWithoutLastParagraph = remainingText.substring(
            0,
            remainingText.length - paragraphs[paragraphs.length - 1].length,
          );
          const newText = queuedTextSoFar
            ? queuedTextSoFar + remainingTextWithoutLastParagraph
            : remainingTextWithoutLastParagraph;
          set({ queuedTextSoFar: newText });
          enqueueText(fullParagraphs);
        }
      } else {
        set({ queuedTextSoFar: '' });
        enqueueText(remainingText);
      }
    } else {
      console.log('Cannot continue reading from a different text', "'", queuedTextSoFar, "'", "'", text, "'");
      throw new Error('Cannot continue reading from a different text');
    }
  },

  stopReading: () => {
    get().soundsToPlayQueue.forEach((sound) => sound.promise.then((s) => s.stop()));

    set({
      isVoiceModeEnabled: false,
      soundsToPlayQueue: [],
      isPlaying: false,
    });
  },

  startRecording: () => {
    if (get().isRecording) return;

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        console.log('Recording started');
        set({ isRecording: true });
        const recorder: MediaRecorder = new MediaRecorder(stream);
        set({ mediaRecorder: recorder });
        recorder.start();

        startCheckingForSilence(stream);

        recorder.addEventListener('dataavailable', async (event) => {
          // Ensure the blob is available before checking

          if (get().isVoiceModeEnabled) {
            if (await detectVoice(event.data)) {
              set({ recordedVoice: event.data });
            } else {
              set({ isVoiceModeEnabled: false });
              useToastsStore.getState().showToast({ title: 'No voice detected', message: 'Turning off voice chat' });
            }
          }

          recorder.stream.getTracks().forEach((t) => t.stop());
          set({ mediaRecorder: undefined });
        });
      })
      .catch((err: DOMException) => {
        console.log(err.name, err.message);
        //TODO: Propagate error to user
      });
  },

  stopRecording: () => {
    const { mediaRecorder } = get();
    if (mediaRecorder) {
      mediaRecorder.stop();
    }

    console.log('Recording stopped');
    set({ isRecording: false, isRecordingPaused: false });
  },
}));
