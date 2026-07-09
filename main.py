import webview
from webview import FileDialog
import os
import sys
import threading
import json
import shutil
import stat
from pathlib import Path
import configparser
import warnings
import subprocess
import tempfile
warnings.filterwarnings("ignore", message=".*set_audio_backend.*")

# Lazy imports - only import heavy libraries when actually needed

# Store engines outside the Api class to avoid serialization issues
_engine_cache = {}

# Settings file path (in the application directory)
def get_settings_file_path():
    """Get the path to the settings .ini file."""
    if getattr(sys, 'frozen', False):
        # If running as a compiled executable
        application_path = os.path.dirname(sys.executable)
    else:
        # If running as a script
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, 'settings.ini')

class Api:
    def __init__(self):
        self.active_jobs = {}  # {file_path: {"progress": float, "status": str, "message": str}}
        self.processing_queue = []  # Queue for sequential processing
        self.is_processing = False  # Flag to prevent parallel processing
        self._queue_lock = threading.Lock()  # Lock for queue operations
        self._jobs_lock = threading.Lock()  # Lock for active_jobs access
    
    def _get_engine(self):
        """Get or create the transcription engine (stored outside instance to avoid serialization)."""
        # Lazy import to avoid loading heavy libraries at startup
        from transcriber import TranscriptionEngine
        engine_id = id(self)
        if engine_id not in _engine_cache:
            _engine_cache[engine_id] = TranscriptionEngine()
        return _engine_cache[engine_id]
    
    def getTranscriptionFiles(self):
        """Get all transcription JSON files from Documents/Simple Schedules Transcribe subfolders."""
        base_dir = Path.home() / "Documents" / "Simple Schedules Transcribe"
        json_files = []
        
        if base_dir.exists():
            # Use glob with pattern matching instead of rglob for better performance
            # Only search one level deep to avoid scanning entire directory tree
            try:
                # First try direct subdirectories (most common case)
                for subdir in base_dir.iterdir():
                    if subdir.is_dir():
                        json_file = subdir / "transcription.json"
                        if json_file.exists():
                            relative_path = json_file.relative_to(base_dir)
                            json_files.append(str(relative_path))
            except (OSError, PermissionError):
                # Fallback to rglob if there are permission issues
                for json_file in base_dir.rglob("transcription.json"):
                    relative_path = json_file.relative_to(base_dir)
                    json_files.append(str(relative_path))
        
        return json_files
    
    def saveTranscription(self, relative_path, transcriptionData):
        """
        Save transcription data to a file.
        
        Args:
            relative_path: Relative path from Simple Schedules Transcribe base (e.g., "FolderName/transcription.json")
            transcriptionData: The transcription data to save
        """
        try:
            base_dir = Path.home() / "Documents" / "Simple Schedules Transcribe"
            filepath = base_dir / relative_path
            
            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(transcriptionData, f, indent=2, ensure_ascii=False)
            return {"success": True, "message": "Transcription saved successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def getTranscriptionFileContent(self, relative_path):
        """
        Get the content of a transcription file.
        Used by the frontend to load transcription data.
        
        Args:
            relative_path: Relative path from Simple Schedules Transcribe base (e.g., "FolderName/transcription.json")
        
        Returns:
            Dict with success status and file content or error message
        """
        try:
            base_dir = Path.home() / "Documents" / "Simple Schedules Transcribe"
            filepath = base_dir / relative_path
            
            if not filepath.exists():
                return {"success": False, "message": f"File not found: {relative_path}"}
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = json.load(f)
            
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def getAudioFilePath(self, transcription_relative_path, audio_relative_path):
        """
        Get the full path to an audio file for serving.
        
        Args:
            transcription_relative_path: Relative path to transcription folder (e.g., "FolderName/transcription.json")
            audio_relative_path: Relative path to audio from transcription folder (e.g., "audio.wav")
        
        Returns:
            Full absolute path to the audio file
        """
        base_dir = Path.home() / "Documents" / "Simple Schedules Transcribe"
        transcription_folder = base_dir / Path(transcription_relative_path).parent
        audio_path = transcription_folder / audio_relative_path
        return str(audio_path)

    def deleteTranscription(self, relative_path):
        """
        Delete a transcription (JSON + associated folder) from the Simple Schedules Transcribe directory.

        Args:
            relative_path: Relative path to the transcription JSON (e.g., "MyFolder/transcription.json")
        """
        try:
            base_dir = Path.home() / "Documents" / "Simple Schedules Transcribe"
            base_dir_resolved = base_dir.resolve()
            target_path = (base_dir / relative_path).resolve()

            try:
                target_path.relative_to(base_dir_resolved)
            except ValueError:
                return {"success": False, "message": "Invalid transcription path"}

            if not target_path.exists():
                return {"success": False, "message": "Transcription file not found"}

            folder = target_path.parent
            def _remove_readonly(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    raise

            if folder.exists():
                shutil.rmtree(folder, onerror=_remove_readonly)
            else:
                target_path.unlink()

            return {"success": True, "message": "Transcription deleted"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def getDownloadedModels(self):
        """
        Return information about downloaded (cached) AI models.

        This is used by the settings UI to show which models are occupying disk space.
        """
        try:
            from transcriber import ModelManager
            model_manager = ModelManager()
            models = model_manager.list_cached_models()
            return {"success": True, "models": models}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def deleteModel(self, model_id):
        """
        Delete a downloaded model from the local cache.

        Args:
            model_id: HuggingFace model identifier (e.g. 'KBLab/kb-whisper-small')
        """
        try:
            # Create ModelManager directly without creating full TranscriptionEngine
            from transcriber import ModelManager
            model_manager = ModelManager()
            deleted = model_manager.delete_model_cache(model_id)
            if deleted:
                return {"success": True, "message": f"Deleted model cache for {model_id}"}
            else:
                return {"success": False, "message": f"No cached model found for {model_id}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def openFileDialog(self):
        """Open a file dialog and return the selected file path"""
        file_types = ('Video and Audio Files (*.mp4;*.avi;*.mkv;*.mov;*.wmv;*.flv;*.webm;*.m4v;*.mp3;*.wav;*.m4a;*.flac;*.aac;*.ogg;*.wma;*.aiff)', 'All files (*.*)')
        result = window.create_file_dialog(FileDialog.OPEN, allow_multiple=True, file_types=file_types)
        return result
    
    def getAllProgress(self):
        """Get progress for all active jobs."""
        with self._jobs_lock:
            # Return a copy to avoid race conditions with webview serialization
            # Ensure all values are serializable (no None values)
            result = {}
            for file_path, job_data in self.active_jobs.items():
                result[file_path] = {
                    "progress": float(job_data.get("progress", 0.0)),
                    "status": str(job_data.get("status", "unknown")),
                    "message": str(job_data.get("message", ""))
                }
            return result
    
    def startTranscription(self, file_paths, language, model_size):
        """
        Start transcription for multiple files.
        
        Args:
            file_paths: List of file paths
            language: "sv" or "en"
            model_size: "tiny", "small", "medium", or "large"
        
        Returns:
            Dict with success status and message
        """
        try:
            # Lazy import to avoid loading heavy libraries at startup
            from transcriber import TranscriptionJob, Language, ModelSize
            
            # Map language string to enum
            lang_map = {
                "sv": Language.SWEDISH,
                "en": Language.ENGLISH
            }
            lang = lang_map.get(language.lower(), Language.SWEDISH)
            
            # Map model size string to enum
            model_map = {
                "tiny": ModelSize.TINY,
                "small": ModelSize.SMALL,
                "medium": ModelSize.MEDIUM,
                "large": ModelSize.LARGE
            }
            model = model_map.get(model_size.lower(), ModelSize.MEDIUM)
            
            # Initialize jobs and add to queue
            with self._queue_lock:
                with self._jobs_lock:
                    for file_path in file_paths:
                        if file_path not in self.active_jobs:
                            self.active_jobs[file_path] = {
                                "progress": 0.0,
                                "status": "pending",
                                "message": "Queued"
                            }
                        
                        # Create job and add to queue
                        job = TranscriptionJob(
                            file_path=file_path,
                            language=lang,
                            model_size=model
                        )
                        self.processing_queue.append((job, file_path))
            
            # Start processing queue if not already running
            if not self.is_processing:
                threading.Thread(target=self._process_queue, daemon=True).start()
            
            return {"success": True, "message": f"Started transcription for {len(file_paths)} file(s)"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def _process_queue(self):
        """Process transcription queue sequentially, one file at a time."""
        self.is_processing = True
        
        while True:
            with self._queue_lock:
                if not self.processing_queue:
                    self.is_processing = False
                    break
                job, file_path = self.processing_queue.pop(0)
            
            self._transcribe_file(job, file_path)
    
    def _transcribe_file(self, job, file_path):
        """Transcribe a single file."""
        try:
            # Ensure job entry exists before starting
            with self._jobs_lock:
                if file_path not in self.active_jobs:
                    self.active_jobs[file_path] = {
                        "progress": 0.0,
                        "status": "processing",
                        "message": "Starting..."
                    }
                else:
                    self.active_jobs[file_path]["status"] = "processing"
            
            def progress_callback(progress, message):
                """Update progress for this file (thread-safe)."""
                try:
                    with self._jobs_lock:
                        if file_path in self.active_jobs:
                            self.active_jobs[file_path]["progress"] = progress * 100
                            self.active_jobs[file_path]["message"] = message
                except Exception:
                    # Silently ignore errors in progress callback to prevent crashes
                    pass
            
            # Run transcription
            engine = self._get_engine()
            result = engine.transcribe(job, progress_callback)
            
            # Update final status
            with self._jobs_lock:
                if file_path in self.active_jobs:
                    if result.error:
                        self.active_jobs[file_path]["status"] = "error"
                        self.active_jobs[file_path]["message"] = result.error
                    else:
                        # Save result (creates folder and saves both JSON and WAV)
                        json_path = engine.save_result(result)

                        # Fill in Summary / Decisions / Action items via Claude Code
                        # (runs on the subscription, not the paid API). Fail-safe:
                        # a failure just leaves the sections blank.
                        try:
                            from meeting_summary import enrich_json
                            enrich_json(json_path)
                        except Exception as _sum_err:
                            print(f"Summary skipped: {_sum_err}")

                        # Auto-export a Markdown copy into the Simple-Schedules-Meet
                        # repo, filed under its day folder. Fail-safe: never let a
                        # failed export break a completed transcription.
                        try:
                            from meet_export import export_to_meet
                            export_to_meet(json_path)
                        except Exception as _meet_err:
                            print(f"Meet auto-export skipped: {_meet_err}")

                        # Auto-share the transcript's Markdown into Slack (#möte).
                        # Fail-safe: never let a Slack hiccup break a completed job.
                        try:
                            from slack_export import post_to_slack
                            post_to_slack(json_path)
                        except Exception as _slack_err:
                            print(f"Slack post skipped: {_slack_err}")

                        self.active_jobs[file_path]["status"] = "completed"
                        self.active_jobs[file_path]["progress"] = 100.0
                        self.active_jobs[file_path]["message"] = "Complete"
        except Exception as e:
            # Ensure we can update error status even if job entry is missing
            try:
                with self._jobs_lock:
                    if file_path not in self.active_jobs:
                        self.active_jobs[file_path] = {
                            "progress": 0.0,
                            "status": "error",
                            "message": str(e)
                        }
                    else:
                        self.active_jobs[file_path]["status"] = "error"
                        self.active_jobs[file_path]["message"] = str(e)
            except Exception:
                # If even error handling fails, log it but don't crash
                print(f"Critical error updating job status for {file_path}: {e}")
    
    def getSettings(self):
        """
        Get application settings from the .ini file.
        
        Returns:
            Dict with 'language' and 'theme' keys, or defaults if file doesn't exist
        """
        settings_file = get_settings_file_path()
        config = configparser.ConfigParser()
        
        # Default settings
        defaults = {
            'language': 'sv',
            'theme': 'light'
        }
        
        # Try to read existing settings
        if os.path.exists(settings_file):
            try:
                config.read(settings_file, encoding='utf-8')
                if 'Settings' in config:
                    settings = {}
                    settings['language'] = config.get('Settings', 'language', fallback=defaults['language'])
                    settings['theme'] = config.get('Settings', 'theme', fallback=defaults['theme'])
                    return settings
            except Exception as e:
                print(f"Error reading settings file: {e}")
                return defaults
        
        # Return defaults if file doesn't exist or error occurred
        return defaults
    
    def saveSettings(self, settings):
        """
        Save application settings to the .ini file.
        
        Args:
            settings: Dict with 'language' and 'theme' keys
        
        Returns:
            Dict with success status and message
        """
        try:
            settings_file = get_settings_file_path()
            config = configparser.ConfigParser()
            
            # Read existing config if it exists
            if os.path.exists(settings_file):
                config.read(settings_file, encoding='utf-8')
            
            # Ensure 'Settings' section exists
            if 'Settings' not in config:
                config.add_section('Settings')
            
            # Update settings
            config.set('Settings', 'language', str(settings.get('language', 'sv')))
            config.set('Settings', 'theme', str(settings.get('theme', 'light')))
            
            # Write to file
            with open(settings_file, 'w', encoding='utf-8') as f:
                config.write(f)
            
            return {"success": True, "message": "Settings saved successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def openTranscriptionAsText(self, transcriptionData):
        """
        Export transcription data to a plain-text file and open it in the
        operating system's default text application.

        Cross-platform: uses `open` on macOS, `xdg-open` on Linux, and
        `os.startfile` on Windows.

        Args:
            transcriptionData: The transcription data dictionary

        Returns:
            Dict with success status and message
        """
        try:
            # Format the transcription data for Notepad
            lines = []
            
            # Title
            lines.append(f"{transcriptionData.get('title', 'Untitled Transcription')}")
            lines.append("=" * 60)
            lines.append("")
            
            # Date and time
            date = transcriptionData.get('date', '')
            time = transcriptionData.get('time', '')
            if date or time:
                date_time_str = f"{date} {time}".strip()
                lines.append(f"Date: {date_time_str}")
                lines.append("")
            
            # Speakers
            speakers = transcriptionData.get('speakers', [])
            if speakers:
                lines.append(f"Speakers: {', '.join(speakers)}")
                lines.append("")
            
            lines.append("-" * 60)
            lines.append("")
            
            # Transcription entries
            transcribed_text = transcriptionData.get('transcribedText', [])
            for entry in transcribed_text:
                timestamp = entry.get('timestamp', '')
                speaker_index = entry.get('speakerIndex', 0)
                text = entry.get('text', '')
                
                # Formated timestamp (removing leading zeros from hours if 00:)
                timestamp_parts = timestamp.split(':')
                if len(timestamp_parts) == 3:
                    hours, minutes, seconds = timestamp_parts
                    if hours == '00':
                        formatted_timestamp = f"{minutes}:{seconds}"
                    else:
                        formatted_timestamp = f"{int(hours)}:{minutes}:{seconds}"
                else:
                    formatted_timestamp = timestamp
                
                speaker_name = speakers[speaker_index] if speaker_index < len(speakers) else f"Speaker {speaker_index + 1}"
                
                lines.append(f"[{formatted_timestamp}] {speaker_name}:")
                lines.append(f"{text}")
                lines.append("")
            
            # Write to a readable temp file (prefix keeps it recognisable on disk)
            safe_title = str(transcriptionData.get('title', 'transcription'))
            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in safe_title).strip() or 'transcription'
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix=f'{safe_title} - ', suffix='.txt', delete=False) as f:
                f.write('\n'.join(lines))
                temp_file_path = f.name

            # Open in the OS default text application (cross-platform)
            if sys.platform == 'darwin':
                subprocess.Popen(['open', temp_file_path])
            elif sys.platform == 'win32':
                os.startfile(temp_file_path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(['xdg-open', temp_file_path])

            return {"success": True, "message": "Opened transcription as text"}
        except Exception as e:
            return {"success": False, "message": str(e)}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    html_file_path = resource_path('index.html')
    api = Api()
    
    global window
    window = webview.create_window(
        'Simple Schedules Transcribe',
        url=f'file://{html_file_path}',
        min_size=(800, 600),
        js_api=api,
        easy_drag=True
    )
    
    webview.start(debug=False)

if __name__ == '__main__':
    main()