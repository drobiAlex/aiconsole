import { create } from 'zustand';
import { AudioAPI } from '@/api/api/AudioAPI';
import { detectVoice } from './detectVoice';
import { useToastsStore } from '@/store/common/useToastsStore';
import { startCheckingForSilence } from './startCheckingForSilence';

interface SoundPromise {
  promise: Promise<Howl>;
  isFinished: boolean;
}

export type MediaAudioTrackConstraints = Pick<
  MediaTrackConstraints,
  | 'deviceId'
  | 'groupId'
  | 'autoGainControl'
  | 'channelCount'
  | 'echoCancellation'
  | 'noiseSuppression'
  | 'sampleRate'
  | 'sampleSize'
>;

interface AudioState {
  soundsToPlayQueue: SoundPromise[];
  isVoiceModeEnabled: boolean;
  isPlaying: boolean;
  numLoading: number;
  queuedTextSoFar: string;
  enqueueText: (text: string) => Promise<void>;
  processQueue: () => Promise<void>;
  readText: (text: string, canBeContinued: boolean) => Promise<void>;
  stopReading: () => void;
  startRecording: () => void;
  stopRecording: () => void;
  togglePauseResumeRecording: () => void;
  recordingBlob?: Blob;
  isRecording: boolean;
  isPlayingPaused: boolean;
  isRecordingPaused: boolean;
  recordingTime: number;
  mediaRecorder?: MediaRecorder;
  timerInterval?: NodeJS.Timeout;
  audioTrackConstraints?: MediaAudioTrackConstraints;
  mediaRecorderOptions?: MediaRecorderOptions;
  onNotAllowedOrFound?: (err: DOMException) => void;
}

function _stopTimer() {
  if (useAudioStore.getState().timerInterval != null) {
    clearInterval(useAudioStore.getState().timerInterval);
  }
  useAudioStore.setState({ timerInterval: undefined });
}

function _startTimer() {
  const interval = setInterval(() => {
    useAudioStore.setState((state) => ({ recordingTime: state.recordingTime + 1 }));
  }, 1000);
  useAudioStore.setState({ timerInterval: interval });
}

function stopRecording() {
  const { mediaRecorder } = useAudioStore.getState();
  if (mediaRecorder) {
    mediaRecorder.stop();
  }
  _stopTimer();
  useAudioStore.setState({ recordingTime: 0, isRecording: false, isRecordingPaused: false });
}

export const useAudioStore = create<AudioState>((set, get) => ({
  soundsToPlayQueue: [],
  isVoiceModeEnabled: false,
  isPlaying: false,
  isRecordingPaused: false,
  numLoading: 0,
  queuedTextSoFar: '',
  recorderControls: undefined,
  audioTrackConstraints: undefined,
  mediaRecorderOptions: undefined,

  isRecording: false,
  isPlayingPaused: false,
  recordingTime: 0,
  mediaRecorder: undefined,
  timerInterval: undefined,
  recordingBlob: undefined,

  enqueueText: async (text: string) => {
    console.log('Enqueuing text:', text);

    const newSoundPromise: SoundPromise = {
      promise: AudioAPI.textToSpeech(text),
      isFinished: false,
    };
    set((state) => ({ numLoading: state.numLoading + 1 }));

    const after = () => {
      set((state) => ({ numLoading: state.numLoading - 1 }));
      newSoundPromise.isFinished = true;
      get().processQueue();
    };

    newSoundPromise.promise.then(after, after);
    set((state) => ({ soundsToPlayQueue: [...state.soundsToPlayQueue, newSoundPromise] }));

    if (!get().isPlaying) {
      get().processQueue();
    }
  },

  processQueue: async () => {
    const { soundsToPlayQueue: soundQueue, isPlaying, numLoading } = get();
    console.log('Processing queue', soundQueue.length, isPlaying, numLoading);
    if (soundQueue.length === 0 || !soundQueue[0].isFinished || isPlaying) return;
    const sound: Howl = await soundQueue[0].promise;
    setTimeout(() => {
      sound.once('end', () => {
        set({ isPlaying: false });
        set((state) => ({ soundsToPlayQueue: state.soundsToPlayQueue.slice(1) }));

        //if queue is empty then we are done
        if (get().soundsToPlayQueue.length === 0) {
          const startRecording = get().startRecording;
          if (get().isVoiceModeEnabled && startRecording) {
            startRecording();
          }
        }

        console.log('Sound finished:', sound, soundQueue[0].promise, soundQueue[0].isFinished);
        get().processQueue(); // Process the next item in the queue
      });
      sound.play();
      console.log('Playing sound:', sound);
    }, 100); // delay between sounds
    set({ isPlaying: true });
  },

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
          get().enqueueText(fullParagraphs);
        }
      } else {
        set({ queuedTextSoFar: '' });
        get().enqueueText(remainingText);
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
    if (get().timerInterval != null) return;

    navigator.mediaDevices
      .getUserMedia({ audio: get().audioTrackConstraints ?? true })
      .then((stream) => {
        set({ isRecording: true });
        const recorder: MediaRecorder = new MediaRecorder(stream, get().mediaRecorderOptions);
        set({ mediaRecorder: recorder });
        recorder.start();
        _startTimer();

        startCheckingForSilence(stream);

        recorder.addEventListener('dataavailable', async (event) => {
          // Ensure the blob is available before checking

          if (get().isVoiceModeEnabled) {
            if (await detectVoice(event.data)) {
              set({ recordingBlob: event.data });
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
        get().onNotAllowedOrFound?.(err);
      });
  },

  stopRecording,

  togglePauseResumeRecording: () => {
    if (get().isRecordingPaused) {
      set({ isRecordingPaused: false });
      get().mediaRecorder?.resume();
      _startTimer();
    } else {
      set({ isRecordingPaused: true });
      _stopTimer();
      get().mediaRecorder?.pause();
    }
  },
}));
