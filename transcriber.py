"""
Clean transcription module for DeskScribe application.
Handles audio transcription with automatic speaker diarization using Resemblyzer.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
import json
import subprocess
import tempfile
import shutil
import sys
import os
from datetime import datetime
import numpy as np
import threading
import time

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from resemblyzer import VoiceEncoder, preprocess_wav
from scipy.io import wavfile


# GUI/detached launches (Finder, dock, `nohup`) don't inherit the shell PATH, so
# tools installed under Homebrew/MacPorts (/opt/homebrew/bin etc.) are invisible to
# subprocesses even when present. Prepend the common locations once at import time
# so anything that shells out (ffmpeg, ffprobe, torch/transformers internals) can
# find them. Only real, missing dirs are added.
def _augment_path() -> None:
    extra = [
        '/opt/homebrew/bin', '/usr/local/bin', '/opt/local/bin',
        '/usr/bin', '/bin', '/snap/bin',
    ]
    current = os.environ.get('PATH', '')
    parts = current.split(os.pathsep)
    missing = [d for d in extra if os.path.isdir(d) and d not in parts]
    if missing:
        os.environ['PATH'] = os.pathsep.join(missing + parts)


_augment_path()

# On Apple Silicon we run on the MPS (GPU) backend. A few Whisper ops aren't
# implemented for MPS yet; this lets them fall back to CPU instead of crashing.
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')


def _select_device_dtype():
    """Pick the fastest available compute backend and a matching dtype.

    Priority: NVIDIA CUDA > Apple MPS (Metal GPU) > CPU. float16 on the GPU
    backends roughly halves memory and speeds up the large model a lot; CPU
    stays on float32 (float16 on CPU is slower, not faster)."""
    if torch.cuda.is_available():
        return 'cuda:0', torch.float16
    mps = getattr(torch.backends, 'mps', None)
    if mps is not None and mps.is_available():
        return 'mps', torch.float16
    return 'cpu', torch.float32


class Language(Enum):
    """Supported languages for transcription."""
    SWEDISH = "sv"
    ENGLISH = "en"
    AUTO = None


class ModelSize(Enum):
    """Model sizes - KBLab for Swedish, OpenAI Whisper for English."""
    TINY = ("KBLab/kb-whisper-tiny", "openai/whisper-tiny")
    SMALL = ("KBLab/kb-whisper-small", "openai/whisper-small")
    MEDIUM = ("KBLab/kb-whisper-medium", "openai/whisper-medium")
    LARGE = ("KBLab/kb-whisper-large", "openai/whisper-large")
    
    def get_model_id(self, language: Language) -> str:
        """Get the appropriate model ID based on language."""
        if language == Language.SWEDISH:
            return self.value[0]
        elif language == Language.ENGLISH:
            return self.value[1]
        else:
            return self.value[0]  # Default to KBLab for auto


@dataclass
class TranscriptionJob:
    """Represents a single file in the transcription queue."""
    file_path: str
    language: Language
    model_size: ModelSize
    output_path: Optional[str] = None
    progress: float = 0.0
    status: str = "pending"


@dataclass
class TranscriptionResult:
    """Result of a transcription job."""
    file_path: str
    title: str
    speakers: List[str]
    date: str
    time: str
    audio_path: str
    transcribed_text: List[Dict[str, Any]]
    error: Optional[str] = None


class AudioConverter:
    """Handles audio format conversion to WAV."""
    
    SUPPORTED_FORMATS = {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
        '.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.wma', '.aiff'
    }
    
    @staticmethod
    def is_supported_format(file_path: str) -> bool:
        return Path(file_path).suffix.lower() in AudioConverter.SUPPORTED_FORMATS
    
    @staticmethod
    def needs_conversion(file_path: str) -> bool:
        return Path(file_path).suffix.lower() != '.wav'
    
    # Common install locations for ffmpeg/ffprobe. GUI/detached launches (Finder,
    # nohup) don't inherit the shell PATH, so /opt/homebrew/bin etc. are invisible
    # even when the binary is installed — we probe these explicitly.
    _EXTRA_BIN_DIRS = [
        '/opt/homebrew/bin',   # Homebrew on Apple Silicon
        '/usr/local/bin',      # Homebrew on Intel macOS
        '/opt/local/bin',      # MacPorts
        '/usr/bin',            # Linux / system
        '/bin',
        '/snap/bin',           # Linux (snap)
    ]

    @staticmethod
    def get_binary_path(binary_name: str) -> str:
        """Resolve the path to a binary (ffmpeg or ffprobe), handling frozen app
        state and GUI launches where the shell PATH isn't inherited."""
        exe = binary_name
        if sys.platform == 'win32' and not exe.endswith('.exe'):
            exe += '.exe'

        if getattr(sys, 'frozen', False):
            # If running as a compiled executable, look in the bundle dir first
            bundled = os.path.join(sys._MEIPASS, exe)
            if os.path.exists(bundled):
                return bundled

        # Trust PATH if the binary is actually resolvable there
        found = shutil.which(exe)
        if found:
            return found

        # PATH didn't have it (common for detached/Finder launches) — probe
        # well-known install locations directly.
        for d in AudioConverter._EXTRA_BIN_DIRS:
            candidate = os.path.join(d, exe)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

        # Last resort: return the bare name and let the caller surface a clear error
        return exe

    @staticmethod
    def get_audio_duration(file_path: str) -> float:
        try:
            ffprobe_cmd = AudioConverter.get_binary_path('ffprobe')
            result = subprocess.run(
                [ffprobe_cmd, '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
                capture_output=True, text=True, check=True
            )
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
            return 0.0
    
    @staticmethod
    def convert_to_wav(input_path: str, output_path: Optional[str] = None, 
                       sample_rate: int = 16000) -> str:
        if output_path is None:
            output_path = str(Path(input_path).with_suffix('.wav'))
        
        ffmpeg_cmd = AudioConverter.get_binary_path('ffmpeg')
        
        try:
            subprocess.run([ffmpeg_cmd, '-version'], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(f"{ffmpeg_cmd} not found. Please install ffmpeg.")
        
        subprocess.run(
            [ffmpeg_cmd, '-y', '-i', input_path, '-ar', str(sample_rate),
             '-ac', '1', '-f', 'wav', output_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return output_path


class ModelManager:
    """Manages model loading and caching."""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = str(cache_dir)
        self.loaded_models: Dict[str, Any] = {}
        self.device, self.dtype = _select_device_dtype()
        self._lock = threading.Lock()  # Thread safety for model loading
    
    def is_model_cached(self, model_id: str) -> bool:
        """
        Check if a given HuggingFace model id has been downloaded to the local cache.
        """
        cache_path = Path(self.cache_dir) / f"models--{model_id.replace('/', '--')}"
        return cache_path.exists()
    
    def load_model(self, model_id: str) -> Any:
        # Thread-safe model loading
        with self._lock:
            if model_id in self.loaded_models:
                return self.loaded_models[model_id]
            
            # Load model directly to device to avoid meta tensor issues
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id,
                dtype=self.dtype,
                use_safetensors=True,
                cache_dir=self.cache_dir
            )
            model.to(self.device)
            self.loaded_models[model_id] = model
            return model
    
    def create_pipeline(self, model_id: str) -> Any:
        model = self.load_model(model_id)
        processor = AutoProcessor.from_pretrained(model_id)
        return pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            dtype=self.dtype,
            device=self.device,
            return_timestamps=True
        )

    def list_cached_models(self) -> List[Dict[str, Any]]:
        """
        List all downloaded models that correspond to the known ModelSize/Language
        combinations used by the application.

        Returns:
            List of dicts with keys:
              - modelId: HuggingFace model id (str)
              - language: 'sv' or 'en'
              - modelSize: one of 'tiny', 'small', 'medium', 'large'
              - cachePath: absolute path to the cache directory for the model
              - sizeBytes: total size on disk for the cached model (int)
        """
        results: List[Dict[str, Any]] = []
        cache_root = Path(self.cache_dir)

        if not cache_root.exists():
            return results

        for size in ModelSize:
            for language in (Language.SWEDISH, Language.ENGLISH):
                model_id = size.get_model_id(language)
                folder_name = f"models--{model_id.replace('/', '--')}"
                folder_path = cache_root / folder_name
                if not folder_path.exists():
                    continue

                # Calculate total size of the cached model
                total_size = 0
                for path in folder_path.rglob("*"):
                    if path.is_file():
                        try:
                            total_size += path.stat().st_size
                        except OSError:
                            # Ignore files we cannot stat for any reason
                            continue

                results.append(
                    {
                        "modelId": model_id,
                        "language": language.value or "auto",
                        "modelSize": size.name.lower(),
                        "cachePath": str(folder_path.resolve()),
                        "sizeBytes": total_size,
                    }
                )

        return results

    def delete_model_cache(self, model_id: str) -> bool:
        """
        Delete the cached files for a given HuggingFace model id.

        Args:
            model_id: HuggingFace model identifier (e.g. 'KBLab/kb-whisper-small')

        Returns:
            True if a cache directory was found and removed, False otherwise.
        """
        cache_root = Path(self.cache_dir)
        folder_name = f"models--{model_id.replace('/', '--')}"
        folder_path = cache_root / folder_name

        if not folder_path.exists():
            return False

        # Remove from in-memory cache if loaded
        with self._lock:
            if model_id in self.loaded_models:
                # Let Python/torch handle actual memory freeing; we just drop the reference.
                del self.loaded_models[model_id]

        shutil.rmtree(folder_path, ignore_errors=True)
        return True


class SpeakerDiarizer:
    """Handles speaker diarization using Resemblyzer."""
    
    def __init__(self):
        self._encoder = None  # Lazy-loaded
    
    @property
    def encoder(self):
        """Lazy-load the VoiceEncoder only when needed."""
        if self._encoder is None:
            self._encoder = VoiceEncoder()
        return self._encoder
    
    def diarize(self, audio_path: str, transcription_segments: List[Dict],
                progress_callback: Optional[Callable[[float, str], None]] = None) -> List[Dict]:
        """Perform speaker diarization using transcription segments directly."""
        if not transcription_segments:
            return []
        
        # Load audio
        sample_rate, audio_raw = wavfile.read(audio_path)
        audio = self._normalize_audio(audio_raw)
        
        if progress_callback:
            progress_callback(0.0, "Extracting speaker embeddings...")
        
        # Extract embeddings for each transcription segment
        embeddings = []
        valid_segments = []
        
        for i, segment in enumerate(transcription_segments):
            start, end = self._get_timestamps(segment)
            if start is None or end is None or end <= start:
                continue
            
            segment_audio = self._extract_segment(audio, start, end, sample_rate)
            if len(segment_audio) < sample_rate * 0.3:  # Skip very short segments
                continue
            
            try:
                segment_wav = preprocess_wav(segment_audio, source_sr=sample_rate)
                embeddings.append(self.encoder.embed_utterance(segment_wav))
                valid_segments.append((start, end))
                if progress_callback:
                    progress_callback((i + 1) / len(transcription_segments) * 0.5, 
                                    f"Processing segment {i+1}/{len(transcription_segments)}...")
            except Exception:
                continue
        
        if not embeddings:
            return [{"speaker": "Speaker 0", "start": self._get_timestamps(s)[0] or 0, 
                    "end": self._get_timestamps(s)[1] or 0} for s in transcription_segments]
        
        # Cluster embeddings
        if progress_callback:
            progress_callback(0.5, "Clustering speakers...")
        
        labels = self._cluster(embeddings, progress_callback)
        
        # Assign speakers to segments
        if progress_callback:
            progress_callback(0.9, "Assigning speakers...")
        
        speaker_segments = []
        label_idx = 0
        
        for segment in transcription_segments:
            start, end = self._get_timestamps(segment)
            if start is None or end is None:
                continue
            
            if label_idx < len(valid_segments):
                v_start, v_end = valid_segments[label_idx]
                if abs(start - v_start) < 0.05 and abs(end - v_end) < 0.05:
                    speaker_segments.append({
                        "speaker": f"Speaker {labels[label_idx]}",
                        "start": start,
                        "end": end
                    })
                    label_idx += 1
                else:
                    speaker_segments.append({"speaker": "Speaker 0", "start": start, "end": end})
            else:
                speaker_segments.append({"speaker": "Speaker 0", "start": start, "end": end})
        
        if progress_callback:
            progress_callback(1.0, "Speaker diarization complete")
        
        return speaker_segments
    
    def _normalize_audio(self, audio_raw: np.ndarray) -> np.ndarray:
        """Convert integer audio to floating-point."""
        if audio_raw.dtype in (np.float32, np.float64):
            return audio_raw
        if audio_raw.dtype == np.int16:
            return audio_raw.astype(np.float32) / 32768.0
        elif audio_raw.dtype == np.int32:
            return audio_raw.astype(np.float32) / 2147483648.0
        else:
            return audio_raw.astype(np.float32) / np.iinfo(audio_raw.dtype).max
    
    def _get_timestamps(self, segment: Dict) -> tuple:
        """Extract start and end timestamps from segment."""
        if "timestamp" in segment and isinstance(segment["timestamp"], tuple):
            return segment["timestamp"]
        return segment.get("start", 0), segment.get("end", 0)
    
    def _extract_segment(self, audio: np.ndarray, start: float, end: float, 
                        sample_rate: int) -> np.ndarray:
        """Extract audio segment."""
        start_sample = int(start * sample_rate)
        end_sample = min(int(end * sample_rate), len(audio))
        return audio[start_sample:end_sample] if end_sample > start_sample else np.array([])
    
    def _cluster(self, embeddings: List[np.ndarray], 
                progress_callback: Optional[Callable] = None) -> List[int]:
        """Cluster embeddings to identify speakers."""
        if len(embeddings) < 2:
            return [0] * len(embeddings)
        
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics import silhouette_score
        from sklearn.metrics.pairwise import cosine_similarity
        
        embeddings_array = np.array(embeddings)
        
        # Calculate similarity metrics
        if len(embeddings) > 50:
            sample_indices = np.random.choice(len(embeddings), min(30, len(embeddings)), replace=False)
            similarities = cosine_similarity(embeddings_array[sample_indices])[
                np.triu_indices(len(sample_indices), k=1)]
        else:
            similarities = cosine_similarity(embeddings_array)[np.triu_indices(len(embeddings), k=1)]
        
        avg_similarity = np.mean(similarities)
        min_similarity = np.min(similarities)
        
        # Test different cluster counts
        max_speakers = min(10, len(embeddings))
        scores = {}
        
        for n_clusters in range(1, max_speakers + 1):
            if progress_callback:
                progress_callback(0.5 + (n_clusters / max_speakers) * 0.3, 
                                f"Testing {n_clusters} speakers...")
            
            clustering = AgglomerativeClustering(n_clusters=n_clusters)
            labels = clustering.fit_predict(embeddings_array)
            
            if n_clusters == 1:
                scores[1] = 0.28 if avg_similarity > 0.85 else (0.12 if avg_similarity > 0.75 
                                                                else (0.0 if avg_similarity > 0.65 else -0.15))
            else:
                scores[n_clusters] = silhouette_score(embeddings_array, labels)
        
        # Find best number of clusters
        best_n = 1
        best_score = scores[1]
        
        for n in range(2, max_speakers + 1):
            penalty = 0.01 if n == 2 else (n - 2) * 0.03 + 0.01
            if scores[n] - penalty > best_score:
                best_score = scores[n] - penalty
                best_n = n
        
        # Final validation: revert to 1 speaker if similarity is extremely high
        if best_n > 1 and avg_similarity > 0.92 and min_similarity > 0.80:
            if scores[best_n] < 0.2 and scores[1] > scores[best_n] + 0.1:
                best_n = 1
                if progress_callback:
                    progress_callback(0.8, "Extremely high similarity - using 1 speaker...")
        
        if progress_callback:
            progress_callback(0.8, f"Using {best_n} speaker(s)...")
        
        clustering = AgglomerativeClustering(n_clusters=best_n)
        return clustering.fit_predict(embeddings_array).tolist()


class TranscriptionEngine:
    """Main transcription engine coordinating all components."""
    
    def __init__(self, output_base_dir: Optional[str] = None):
        if output_base_dir is None:
            # Use Documents/Simple Schedules Transcribe as default
            output_base_dir = Path.home() / "Documents" / "Simple Schedules Transcribe"
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        self.model_manager = ModelManager()
        self._diarizer = None  # Lazy-loaded
        self.temp_dir = Path(tempfile.mkdtemp())
    
    @property
    def diarizer(self):
        """Lazy-load the SpeakerDiarizer only when needed."""
        if self._diarizer is None:
            self._diarizer = SpeakerDiarizer()
        return self._diarizer
    
    def transcribe(self, job: TranscriptionJob, 
                   progress_callback: Optional[Callable[[float, str], None]] = None) -> TranscriptionResult:
        """Transcribe a single audio file with automatic speaker diarization."""
        try:
            if progress_callback:
                progress_callback(0.05, "Checking model availability...")
            
            model_id = job.model_size.get_model_id(job.language)
            
            if progress_callback:
                progress_callback(0.15, "Preparing audio file...")
            
            if not AudioConverter.is_supported_format(job.file_path):
                raise ValueError(f"Unsupported file format: {Path(job.file_path).suffix}")
            
            # Always convert to WAV for processing and saving
            if progress_callback:
                progress_callback(0.16, "Converting audio to WAV format...")
            
            # Ensure temp_dir exists
            if not self.temp_dir.exists():
                self.temp_dir.mkdir(parents=True, exist_ok=True)
            
            wav_path = str(self.temp_dir / f"{Path(job.file_path).stem}.wav")
            audio_path = AudioConverter.convert_to_wav(job.file_path, wav_path)
            
            # Validate audio_path was created successfully
            if not audio_path or not Path(audio_path).exists():
                raise RuntimeError(f"Failed to convert audio file: {job.file_path}")
            
            audio_duration = AudioConverter.get_audio_duration(audio_path)
            
            if progress_callback:
                progress_callback(0.2, "Starting transcription...")
            
            # Transcribe
            transcription_progress = {'value': 0.2}
            stop_event = threading.Event()
            
            def estimate_progress():
                estimated_time = audio_duration * 0.2
                start_time = time.time()
                while not stop_event.is_set():
                    elapsed = time.time() - start_time
                    if estimated_time > 0:
                        transcription_progress['value'] = min(0.2 + (elapsed / estimated_time) * 0.45, 0.65)
                    time.sleep(0.5)
            
            progress_thread = threading.Thread(target=estimate_progress)
            progress_thread.start()
            
            try:
                pipe = self.model_manager.create_pipeline(model_id)
                language = job.language.value if job.language != Language.AUTO else None
                result = pipe(
                    audio_path,
                    chunk_length_s=30,
                    generate_kwargs={"task": "transcribe", "language": language}
                )
            finally:
                stop_event.set()
                progress_thread.join()
            
            # Normalize segments
            raw_segments = result.get("segments", result.get("chunks", []))
            segments = [self._normalize_segment(seg) for seg in raw_segments]
            
            if progress_callback:
                progress_callback(0.65, "Transcription complete. Starting speaker diarization...")
            
            # Speaker diarization
            def diarization_wrapper(progress: float, message: str):
                if progress_callback:
                    progress_callback(0.65 + (progress * 0.3), message)
            
            diarization = self.diarizer.diarize(audio_path, segments, diarization_wrapper)
            
            # Combine results
            if progress_callback:
                progress_callback(0.95, "Combining results...")
            
            combined = self._combine(segments, diarization)
            
            # Format output
            if progress_callback:
                progress_callback(0.98, "Finalizing...")
            
            result = self._format_result(job, combined, audio_path)
            
            if progress_callback:
                progress_callback(1.0, "Complete!")
            
            return result
            
        except Exception as e:
            return TranscriptionResult(
                file_path=job.file_path,
                title="", speakers=[], date="", time="", audio_path="",
                transcribed_text=[], error=str(e)
            )
    
    def _normalize_segment(self, seg: Dict) -> Dict:
        """Normalize segment format."""
        normalized = {
            "text": seg.get("text", "").strip(),
            "start": seg.get("start", 0),
            "end": seg.get("end", 0)
        }
        if "timestamp" in seg and isinstance(seg["timestamp"], tuple):
            normalized["start"], normalized["end"] = seg["timestamp"]
        return normalized
    
    def _combine(self, segments: List[Dict], diarization: List[Dict]) -> List[Dict]:
        """Combine transcription segments with speaker diarization."""
        diarization_map = {(round(d["start"], 3), round(d["end"], 3)): d["speaker"] 
                          for d in diarization}
        
        combined = []
        for segment in segments:
            start, end = segment.get("start", 0), segment.get("end", 0)
            text = segment.get("text", "").strip()
            
            if start is None or end is None or not text:
                continue
            
            key = (round(start, 3), round(end, 3))
            speaker = diarization_map.get(key, "Speaker 0")
            
            # Fallback: find closest match
            if speaker == "Speaker 0":
                for d in diarization:
                    if abs(d["start"] - start) < 0.01 and abs(d["end"] - end) < 0.01:
                        speaker = d["speaker"]
                        break
            
            combined.append({"text": text, "speaker": speaker, "start": start, "end": end})
        
        return combined
    
    def _format_result(self, job: TranscriptionJob, combined: List[Dict],
                       wav_audio_path: str) -> TranscriptionResult:
        """Format result into expected JSON structure."""
        speakers = sorted(list(set(entry["speaker"] for entry in combined)))
        speaker_map = {speaker: idx for idx, speaker in enumerate(speakers)}
        
        transcribed_text = []
        for entry in combined:
            timestamp = self._format_timestamp(entry["start"])
            transcribed_text.append({
                "text": entry["text"],
                "speakerIndex": speaker_map[entry["speaker"]],
                "timestamp": timestamp
            })
        
        # Merge consecutive entries from the same speaker to make frontend look better :p
        merged_text = []
        for entry in transcribed_text:
            if merged_text and merged_text[-1]["speakerIndex"] == entry["speakerIndex"]:
                # Merge with previous entry: combine text, keep original timestamp
                merged_text[-1]["text"] += " " + entry["text"]
            else:
                # New entry (different speaker or first entry)
                merged_text.append(entry)
        
        filename = Path(job.file_path).stem
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        
        # Store the WAV path for saving later
        return TranscriptionResult(
            file_path=job.file_path,
            title=filename.replace("_", " ").title(),
            speakers=speakers,
            date=date_str,
            time=time_str,
            audio_path=wav_audio_path,  # Store the WAV path temporarily
            transcribed_text=merged_text
        )
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds to HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def save_result(self, result: TranscriptionResult, folder_name: Optional[str] = None):
        """Save transcription result to a folder with JSON and WAV files."""
        if result.error:
            raise ValueError(f"Cannot save transcription with error: {result.error}")
        
        # Create folder name for this transcription
        if folder_name is None:
            # Use title to create folder name
            safe_title = "".join(c for c in result.title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')
            base_folder_name = safe_title
            
            # Handle duplicate folder names by appending a number
            folder_name = base_folder_name
            counter = 1
            while (self.output_base_dir / folder_name).exists():
                folder_name = f"{base_folder_name}_{counter}"
                counter += 1
        
        # Create transcription folder
        transcription_folder = self.output_base_dir / folder_name
        transcription_folder.mkdir(parents=True, exist_ok=True)
        
        # Copy WAV file to transcription folder
        if not result.audio_path:
            raise ValueError("Cannot save transcription: audio_path is missing")
        
        wav_source = Path(result.audio_path)
        wav_dest = transcription_folder / "audio.wav"
        if wav_source.exists():
            shutil.copy2(wav_source, wav_dest)
        else:
            # Log warning but continue - audio file might have been cleaned up
            print(f"Warning: Audio file not found at {result.audio_path}, skipping copy")
        
        # Save JSON file
        json_path = transcription_folder / "transcription.json"
        
        # Update audioPath to be relative to the JSON file
        audio_path_relative = "audio.wav"
        
        data = {
            "title": result.title,
            "speakers": result.speakers,
            "date": result.date,
            "time": result.time,
            "audioPath": audio_path_relative,
            "transcribedText": result.transcribed_text
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(json_path)
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
