class AudioCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const d = input[0];
    const pcm = new Int16Array(d.length);
    for (let i = 0; i < d.length; i++) {
      const s = Math.max(-1, Math.min(1, d[i]));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    this.port.postMessage({ type: 'audio', data: pcm });
    return true;
  }
}
registerProcessor('audio-capture-processor', AudioCaptureProcessor);
