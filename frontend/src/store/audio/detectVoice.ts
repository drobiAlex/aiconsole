/**
 * Detects voice in an audio blob by analyzing audio samples.
 * Assumes mono audio input.
 *
 * @param {Blob} blob - The audio blob to analyze.
 * @returns {Promise<boolean>} - True if voice is detected, false otherwise.
 */
export const detectVoice = async (blob: Blob) => {
  //@ts-expect-error - webkitAudioContext is not in the types
  const audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const arrayBuffer = await blob.arrayBuffer();
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
  const rawData = audioBuffer.getChannelData(0); // Assuming mono audio
  const blockSize = Math.floor(rawData.length / 100); // Divide the audio into 100 blocks
  let voiceDetected = false;

  for (let i = 0; i < 100; i++) {
    const blockStart = blockSize * i; // the position to start the block
    let sum = 0;
    for (let j = 0; j < blockSize; j++) {
      sum += Math.abs(rawData[blockStart + j]); // summing the absolute values of the audio samples
    }
    const average = sum / blockSize;
    const threshold = 0.001; // Threshold for determining voice presence, adjust based on testing

    if (average > threshold) {
      voiceDetected = true;
      break; // Stop checking if we've already found voice
    }
  }

  audioContext.close();
  return voiceDetected;
};
