#!/usr/bin/env python3

"""
Test script to verify the new features work
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from application import BookReaderApplication

def test_application():
    """Test that the application can be created and has the expected actions"""
    app = BookReaderApplication()
    
    # Check that all actions exist
    expected_actions = ["preferences", "about", "quit", "open", "shortcuts"]
    for action_name in expected_actions:
        action = app.lookup_action(action_name)
        assert action is not None, f"Action {action_name} not found"
        print(f"✓ Action {action_name} exists")
    
    # Check keyboard shortcuts are registered
    shortcuts = {
        "app.quit": ["<Control>q"],
        "app.open": ["<Control>o"],
        "app.preferences": ["<Control>comma"],
        "app.shortcuts": ["<Control>question"]
    }
    
    for action, expected_accels in shortcuts.items():
        accels = app.get_accels_for_action(action)
        assert list(accels) == expected_accels, f"Wrong shortcuts for {action}: got {list(accels)}, expected {expected_accels}"
        print(f"✓ Shortcuts for {action}: {list(accels)}")
    
    print("✓ All application tests passed!")
    return app

def test_window_actions(app):
    """Test window actions"""
    # Create a window to test
    window = app.window
    if not window:
        app.activate()
        window = app.window
    
    # Check window actions exist
    expected_actions = ["fullscreen", "search", "back", "prev-page", "next-page", 
                       "first-page", "last-page", "font-increase", "font-decrease", "tts-toggle"]
    
    for action_name in expected_actions:
        action = window.lookup_action(action_name)
        assert action is not None, f"Window action {action_name} not found"
        print(f"✓ Window action {action_name} exists")
    
    # Check window shortcuts are registered
    window_shortcuts = {
        "win.fullscreen": ["F11"],
        "win.search": ["<Control>f"],
        "win.back": ["Escape"],
        "win.prev-page": ["Left"],
        "win.next-page": ["Right"],
        "win.first-page": ["Home"],
        "win.last-page": ["End"],
        "win.font-increase": ["plus", "KP_Add"],
        "win.font-decrease": ["minus", "KP_Subtract"],
        "win.tts-toggle": ["space"]
    }
    
    for action, expected_accels in window_shortcuts.items():
        accels = app.get_accels_for_action(action)
        assert list(accels) == expected_accels, f"Wrong shortcuts for {action}: got {list(accels)}, expected {expected_accels}"
        print(f"✓ Window shortcuts for {action}: {list(accels)}")
    
    print("✓ All window tests passed!")

def test_welcome_screen(app):
    """Test welcome screen exists"""
    window = app.window
    if not window:
        app.activate()
        window = app.window
    
    # Check that welcome view exists in stack
    stack = window.main_stack
    welcome_child = stack.get_child_by_name("welcome")
    assert welcome_child is not None, "Welcome screen not found in stack"
    print("✓ Welcome screen exists")
    
    print("✓ Welcome screen test passed!")

def main():
    """Run all tests"""
    print("Testing Folio new features...")
    
    # Create application
    app = test_application()
    
    # Test window (requires activation)
    loop = GLib.MainLoop()
    
    def on_activate(app):
        test_window_actions(app)
        test_welcome_screen(app)
        loop.quit()
    
    app.connect("activate", on_activate)
    
    # Run briefly to test activation
    GLib.timeout_add(100, lambda: loop.quit())
    app.run([])
    
    print("\n🎉 All tests passed! New features are working correctly.")

if __name__ == "__main__":
    main()