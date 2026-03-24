#!/usr/bin/env python3
"""
Simple smoke test for Folio
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that basic modules can be imported"""
    print("Testing imports...")
    
    try:
        # Test core module imports
        import application
        import window
        import library
        import reader
        import book_parser
        import tts
        import settings
        import utils
        print("✓ All modules imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        return False

def test_book_parser():
    """Test book parser with a simple text file"""
    print("Testing book parser...")
    
    try:
        import tempfile
        from book_parser import create_parser, TextParser
        
        # Create test file
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
        return True
    except Exception as e:
        print(f"✗ Book parser test failed: {e}")
        return False

def test_tts_engine():
    """Test TTS engine initialization"""
    print("Testing TTS engine...")
    
    try:
        from tts import TTSEngine
        
        engine = TTSEngine()
        voices = engine.get_available_voices()
        
        print(f"✓ TTS engine initialized, {len(voices)} voices available")
        return True
    except Exception as e:
        print(f"✗ TTS engine test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Running Folio smoke tests...\n")
    
    tests = [
        test_imports,
        test_book_parser,
        test_tts_engine,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! Folio is ready.")
        return 0
    else:
        print("✗ Some tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())