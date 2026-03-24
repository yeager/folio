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
    import os
    
    # Set up internationalization
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    
    # Find locale directory (supports running from source, installed, and Flatpak)
    source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locale_dirs = [
        os.path.join(source_dir, "po"),              # Running from source (compiled .mo)
        os.path.join(source_dir, "locale"),           # Local build
        os.path.join(sys.prefix, "share", "locale"),  # pip install / venv
        "/app/share/locale",                          # Flatpak
        "/usr/share/locale",                          # System install
        "/usr/local/share/locale",                    # Local install
    ]
    
    locale_dir = None
    for d in locale_dirs:
        if os.path.isdir(d):
            locale_dir = d
            break
    
    if locale_dir is None:
        locale_dir = "/usr/share/locale"
    
    # Also compile .po → .mo on the fly if running from source
    po_dir = os.path.join(source_dir, "po")
    if os.path.isdir(po_dir):
        for po_file in os.listdir(po_dir):
            if po_file.endswith(".po") and po_file != "folio.pot":
                lang = po_file[:-3]
                mo_dir = os.path.join(po_dir, lang, "LC_MESSAGES")
                mo_file = os.path.join(mo_dir, "folio.mo")
                po_path = os.path.join(po_dir, po_file)
                if not os.path.exists(mo_file) or \
                   os.path.getmtime(po_path) > os.path.getmtime(mo_file):
                    try:
                        os.makedirs(mo_dir, exist_ok=True)
                        os.system(f'msgfmt -o "{mo_file}" "{po_path}"')
                    except Exception:
                        pass
        locale_dir = po_dir  # Use po/ dir with compiled .mo files
    
    gettext.bindtextdomain("folio", locale_dir)
    gettext.textdomain("folio")
    
    app = BookReaderApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())