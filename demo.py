#!/usr/bin/env python3
"""
Demo script showing Folio's TTS word highlighting
"""

import os
import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gi.repository import Gtk, Adw, GLib
import signal

def demo_word_highlighting():
    """Demo the word-level TTS highlighting"""
    
    # Import Folio modules
    from tts import TTSEngine
    
    print("Folio TTS Word Highlighting Demo")
    print("=" * 40)
    
    # Initialize TTS engine
    engine = TTSEngine()
    
    # Get available voices
    voices = engine.get_available_voices()
    print(f"Available voices: {', '.join(voices)}")
    
    # Test text
    test_text = "Detta är ett test av Folios text-till-tal funktion med ordmarkering."
    words = engine.split_into_words(test_text)
    
    print(f"\nTest text: {test_text}")
    print(f"Words: {words}")
    print(f"Word count: {len(words)}")
    
    # Test word callback simulation
    def word_callback(word_index):
        if word_index < len(words):
            print(f"Highlighting word {word_index}: '{words[word_index]}'")
    
    print("\nWord highlighting simulation:")
    for i, word in enumerate(words):
        word_callback(i)
    
    print("\n✓ TTS word highlighting system is ready!")
    print("✓ Ready for karaoke-style reading experience!")

if __name__ == "__main__":
    demo_word_highlighting()