from faster_whisper import WhisperModel

class AsrEngine:
    def __init__(self, model_size: str = "small", device: str = "cpu") -> None:
        """
        model_size: "tiny" | "base" | "small" | "medium" | "large-v3"
        device: "cpu" | "cuda"
        """
        # compute_type "int8_float16" funciona bien en CPU modernas; en GPU puedes usar "float16"
        self.model = WhisperModel(model_size, device=device)


    def transcribe(self, audio: str, language: str = "es", without_timestamps=True
                        ):

        segments, info = self.model.transcribe(audio, beam_size=5,
            language=language, without_timestamps=without_timestamps, vad_filter=True)

        # Materializar el generador
        segments_list = list(segments)
        # Concatenar texto
        text = " ".join(seg.text.strip() for seg in segments_list)
        confidence = float(getattr(info, "language_probability", 0.0))

        return text, confidence