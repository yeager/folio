#!/usr/bin/env python3
"""
Basic test script to verify Folio can be imported and started
"""

import os
import sys
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, Adw
        print("✓ GTK4 and libadwaita available")
    except Exception as e:
        print(f"✗ GTK4/libadwaita import failed: {e}")
        return False
    
    try:
        from src.application import BookReaderApplication
        from src.window import BookReaderWindow
        from src.library import LibraryView
        from src.reader import ReaderView
        from src.settings import Settings
        from src.book_parser import create_parser
        from src.tts import TTSEngine
        print("✓ All application modules imported successfully")
    except Exception as e:
        print(f"✗ Application import failed: {e}")
        return False
    
    return True

def test_book_parser():
    """Test book parser functionality"""
    print("Testing book parser...")
    
    try:
        from src.book_parser import create_parser, TextParser
        
        # Create a test text file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Chapter 1\n\nThis is a test book.\n\nChapter 2\n\nThis is another chapter.")
            test_file = f.name
        
        parser = create_parser(test_file)
        assert isinstance(parser, TextParser)
        
        metadata = parser.parse()
        assert metadata.title
        assert len(metadata.chapters) > 0
        
        os.unlink(test_file)
        print("✓ Book parser working")
    except Exception as e:
        print(f"✗ Book parser test failed: {e}")
        return False
    
    return True

def test_settings():
    """Test settings functionality"""
    print("Testing settings...")
    
    try:
        from src.settings import Settings
        
        settings = Settings()
        
        # Test basic get/set
        settings.set("test_key", "test_value")
        value = settings.get("test_key")
        assert value == "test_value"
        
        # Test reading position
        settings.set_reading_position("/test/book.epub", 5)
        position = settings.get_reading_position("/test/book.epub")
        assert position == 5
        
        print("✓ Settings working")
    except Exception as e:
        print(f"✗ Settings test failed: {e}")
        return False
    
    return True

def test_tts():
    """Test TTS functionality (without actually speaking)"""
    print("Testing TTS...")
    
    try:
        from src.tts import TTSEngine, get_voice_display_name
        
        tts = TTSEngine()
        
        # Test voice list
        voices = tts.get_available_voices()
        assert isinstance(voices, list)
        
        # Test voice name mapping
        name = get_voice_display_name("sv_SE-nst-medium")
        assert "Svenska" in name or "Swedish" in name
        
        # Test sentence splitting
        sentences = tts.split_into_sentences("Hello world. How are you? Fine!")
        assert len(sentences) == 3
        
        print("✓ TTS engine working (basic functionality)")
    except Exception as e:
        print(f"✗ TTS test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("Bokläsaren Test Suite")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_book_parser,
        test_settings,
        test_tts,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! Bokläsaren should work correctly.")
        return 0
    else:
        print("✗ Some tests failed. Check dependencies and installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())