#!/usr/bin/env python3
"""
Folio - GTK4 e-book reader
Main entry point
"""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GLib
import locale
import gettext

try:
    from .application import BookReaderApplication
except ImportError:
    # When running from source
    from application import BookReaderApplication


def main():
    """Main entry point"""
    # Set up internationalization
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    
    # Set up gettext
    gettext.bindtextdomain("folio", "/usr/share/locale")
    gettext.textdomain("folio")
    
    app = BookReaderApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())