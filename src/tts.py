"""
Text-to-Speech integration with Piper for Folio
"""

import subprocess
import threading
import os
import tempfile
import time
import gettext
import re
from gi.repository import GObject, GLib

_ = gettext.gettext


class TTSEngine(GObject.Object):
    """Text-to-Speech engine using Piper"""
    
    __gsignals__ = {
        'word-started': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'word-finished': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'speech-finished': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'speech-error': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__(self):
        super().__init__()
        self.is_playing = False
        self.is_paused = False
        self.current_process = None
        self.audio_process = None
        self.current_text = ""
        self.current_words = []
        self.current_word_index = 0
        self.voice = "sv_SE-nst-medium"
        self.speed = 1.0
        self.temp_files = []
        
    def get_available_voices(self):
        """Get list of available Piper voices"""
        voices = []
        
        # Common Piper voice locations
        voice_dirs = [
            "/usr/share/piper/voices",
            "/usr/local/share/piper/voices",
            os.path.expanduser("~/.local/share/piper/voices"),
            "/opt/piper/voices"
        ]
        
        for voice_dir in voice_dirs:
            if os.path.exists(voice_dir):
                try:
                    for item in os.listdir(voice_dir):
                        if item.endswith('.onnx'):
                            voice_name = os.path.splitext(item)[0]
                            voices.append(voice_name)
                except:
                    continue
        
        # Default voices if none found
        if not voices:
            voices = [
                "sv_SE-nst-medium",  # Swedish
                "sv_SE-nst-high",
                "en_US-lessac-medium",  # English
                "en_US-lessac-high",
                "en_GB-southern_english_female-medium"
            ]
        
        return sorted(list(set(voices)))
    
    def check_piper_available(self):
        """Check if Piper is available"""
        try:
            result = subprocess.run(['piper', '--help'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def set_voice(self, voice):
        """Set TTS voice"""
        self.voice = voice
    
    def set_speed(self, speed):
        """Set speech speed (0.5 to 2.0)"""
        self.speed = max(0.5, min(2.0, speed))
    
    def split_into_words(self, text):
        """Split text into words for highlighting"""
        # Split into words, preserving order
        words = re.findall(r'\S+', text)
        return words
    
    def speak_text(self, text, words=None):
        """Speak the given text with word-level highlighting"""
        if not text.strip():
            return False
            
        if not self.check_piper_available():
            self.emit('speech-error', _("Piper TTS not available"))
            return False
        
        self.stop()
        
        self.current_text = text
        self.current_words = words or self.split_into_words(text)
        self.current_word_index = 0
        self.is_playing = True
        self.is_paused = False
        
        # Start speech in background thread
        thread = threading.Thread(target=self._speech_worker, args=(text,))
        thread.daemon = True
        thread.start()
        
        return True
    
    def _speech_worker(self, text):
        """Background worker for TTS"""
        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio_path = temp_audio.name
                self.temp_files.append(temp_audio_path)
            
            # Build piper command
            piper_cmd = [
                'piper',
                '--model', self.voice,
                '--output_file', temp_audio_path
            ]
            
            # Add speed control if supported
            if self.speed != 1.0:
                try:
                    # Some Piper versions support --rate
                    piper_cmd.extend(['--rate', str(self.speed)])
                except:
                    pass
            
            # Run Piper to generate audio
            self.current_process = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = self.current_process.communicate(input=text)
            
            if self.current_process.returncode != 0:
                GLib.idle_add(self.emit, 'speech-error', 
                            f"Piper error: {stderr}")
                return
            
            # Play the generated audio
            if self.is_playing:
                self._play_audio(temp_audio_path)
                
        except Exception as e:
            GLib.idle_add(self.emit, 'speech-error', str(e))
        finally:
            self.is_playing = False
            self.current_process = None
            self._cleanup_temp_files()
    
    def _play_audio(self, audio_path):
        """Play audio file and handle word-level highlighting"""
        try:
            # Try different audio players
            audio_players = ['aplay', 'paplay', 'play', 'afplay']
            player_cmd = None
            
            for player in audio_players:
                if subprocess.run(['which', player], capture_output=True).returncode == 0:
                    if player == 'aplay':
                        player_cmd = [player, audio_path]
                    elif player == 'paplay':
                        player_cmd = [player, audio_path]
                    elif player == 'play':
                        player_cmd = [player, audio_path]
                    elif player == 'afplay':  # macOS
                        player_cmd = [player, audio_path]
                    break
            
            if not player_cmd:
                # Fallback: try to use system default
                player_cmd = ['xdg-open', audio_path]
            
            # Start audio playback
            self.audio_process = subprocess.Popen(
                player_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Estimate timing for word highlighting
            if self.current_words:
                # Rough estimation: average characters per word
                total_chars = len(self.current_text)
                words_count = len(self.current_words)
                
                if words_count > 0:
                    # Estimate ~200 WPM (words per minute) base speed, adjusted by speed setting
                    estimated_wpm = 200 * self.speed
                    word_duration = 60.0 / estimated_wpm  # seconds per word
                    
                    # Adjust based on word length (longer words take more time)
                    for i, word in enumerate(self.current_words):
                        if not self.is_playing:
                            break
                        
                        # Scale duration by word length
                        word_time = word_duration * (len(word) / 5.0)  # 5 chars = average word
                        word_time = max(0.1, min(2.0, word_time))  # Clamp between 0.1-2 seconds
                        
                        GLib.idle_add(self.emit, 'word-started', i)
                        time.sleep(word_time)
                        GLib.idle_add(self.emit, 'word-finished', i)
            
            # Wait for audio to finish
            self.audio_process.wait()
            
            if self.is_playing:
                GLib.idle_add(self.emit, 'speech-finished')
                
        except Exception as e:
            GLib.idle_add(self.emit, 'speech-error', str(e))
    
    def pause(self):
        """Pause speech"""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            # Store current position
            self.paused_at_word = self.current_word_index
            if self.audio_process:
                try:
                    self.audio_process.terminate()
                except:
                    pass
    
    def resume(self):
        """Resume speech"""
        if self.is_paused:
            self.is_paused = False
            # Resume from current word position
            if hasattr(self, 'paused_at_word') and self.current_words:
                # Create continuation text from current position
                remaining_words = self.current_words[self.paused_at_word:]
                if remaining_words:
                    continuation_text = " ".join(remaining_words)
                    # Update word index offset
                    word_offset = self.paused_at_word
                    self.current_word_index = word_offset
                    
                    # Start new speech thread for remaining text
                    thread = threading.Thread(target=self._resume_speech_worker, 
                                            args=(continuation_text, word_offset))
                    thread.daemon = True
                    thread.start()
                    
    def _resume_speech_worker(self, text, word_offset):
        """Resume speech from specific word position"""
        # Similar to _speech_worker but with word offset
        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio_path = temp_audio.name
                self.temp_files.append(temp_audio_path)
            
            # Build piper command
            piper_cmd = [
                'piper',
                '--model', self.voice,
                '--output_file', temp_audio_path
            ]
            
            if self.speed != 1.0:
                try:
                    piper_cmd.extend(['--rate', str(self.speed)])
                except:
                    pass
            
            # Run Piper to generate audio
            self.current_process = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = self.current_process.communicate(input=text)
            
            if self.current_process.returncode != 0:
                GLib.idle_add(self.emit, 'speech-error', 
                            f"Piper error: {stderr}")
                return
            
            # Play the generated audio
            if self.is_playing:
                self._play_audio_with_offset(temp_audio_path, word_offset)
                
        except Exception as e:
            GLib.idle_add(self.emit, 'speech-error', str(e))
        finally:
            self.is_playing = False
            self.current_process = None
            self._cleanup_temp_files()
            
    def _play_audio_with_offset(self, audio_path, word_offset):
        """Play audio with word index offset"""
        try:
            # Similar to _play_audio but with offset
            audio_players = ['aplay', 'paplay', 'play', 'afplay']
            player_cmd = None
            
            for player in audio_players:
                if subprocess.run(['which', player], capture_output=True).returncode == 0:
                    if player in ['aplay', 'paplay', 'play', 'afplay']:
                        player_cmd = [player, audio_path]
                    break
            
            if not player_cmd:
                player_cmd = ['xdg-open', audio_path]
            
            # Start audio playback
            self.audio_process = subprocess.Popen(
                player_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Calculate remaining words
            remaining_words = self.current_words[word_offset:] if word_offset < len(self.current_words) else []
            
            if remaining_words:
                estimated_wpm = 200 * self.speed
                word_duration = 60.0 / estimated_wpm
                
                for i, word in enumerate(remaining_words):
                    if not self.is_playing:
                        break
                    
                    actual_word_index = word_offset + i
                    word_time = word_duration * (len(word) / 5.0)
                    word_time = max(0.1, min(2.0, word_time))
                    
                    GLib.idle_add(self.emit, 'word-started', actual_word_index)
                    time.sleep(word_time)
                    GLib.idle_add(self.emit, 'word-finished', actual_word_index)
            
            # Wait for audio to finish
            self.audio_process.wait()
            
            if self.is_playing:
                GLib.idle_add(self.emit, 'speech-finished')
                
        except Exception as e:
            GLib.idle_add(self.emit, 'speech-error', str(e))
    
    def stop(self):
        """Stop speech"""
        self.is_playing = False
        self.is_paused = False
        
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process = None
            except:
                pass
                
        if self.audio_process:
            try:
                self.audio_process.terminate()
                self.audio_process = None
            except:
                pass
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        self.temp_files.clear()
    
    def is_speaking(self):
        """Check if currently speaking"""
        return self.is_playing and not self.is_paused


# Convenience functions for voice management
def get_voice_display_name(voice_id):
    """Get human-readable name for voice"""
    voice_names = {
        'sv_SE-nst-medium': _('Swedish (Alma) - Medium'),
        'sv_SE-nst-high': _('Swedish (Alma) - High Quality'),
        'sv_SE-nst-low': _('Swedish (Alma) - Low Quality'),
        'en_US-lessac-medium': _('English US (Lessac) - Medium'),
        'en_US-lessac-high': _('English US (Lessac) - High Quality'),
        'en_GB-southern_english_female-medium': _('English UK (Female) - Medium'),
        'en_US-libritts-high': _('English US (LibriTTS) - High Quality'),
        'de_DE-thorsten-medium': _('German (Thorsten) - Medium'),
        'es_ES-sharvard-medium': _('Spanish (Sharvard) - Medium'),
        'fr_FR-siwis-medium': _('French (Siwis) - Medium'),
    }
    
    return voice_names.get(voice_id, voice_id)


def get_voice_language(voice_id):
    """Get language code for voice"""
    if voice_id.startswith('sv_'):
        return 'sv'
    elif voice_id.startswith('en_'):
        return 'en'
    elif voice_id.startswith('de_'):
        return 'de'
    elif voice_id.startswith('es_'):
        return 'es'
    elif voice_id.startswith('fr_'):
        return 'fr'
    else:
        return 'en'  # Default to English