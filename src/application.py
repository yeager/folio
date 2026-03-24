"""
Application class for Folio
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib
import gettext
import os

try:
    from .window import BookReaderWindow
    from .settings import Settings
except ImportError:
    # When running from source
    from window import BookReaderWindow
    from settings import Settings

_ = gettext.gettext


class BookReaderApplication(Adw.Application):
    """Main application class"""

    def __init__(self):
        super().__init__(
            application_id="se.danielnylander.folio",
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        
        self.settings = Settings()
        self.window = None
        
        # Set up actions
        self.create_actions()

    def create_actions(self):
        """Create application actions"""
        # Preferences action
        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self.on_preferences_activate)
        self.add_action(prefs_action)
        
        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_activate)
        self.add_action(about_action)
        
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit_activate)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>q"])
        
        # Open file action
        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", self.on_open_activate)
        self.add_action(open_action)
        self.set_accels_for_action("app.open", ["<Ctrl>o"])

    def do_activate(self):
        """Called when the application is activated"""
        if not self.window:
            self.window = BookReaderWindow(application=self)
        self.window.present()

    def do_open(self, files, n_files, hint):
        """Called when the application is asked to open files"""
        self.do_activate()
        if files and len(files) > 0:
            # Open the first file
            file_path = files[0].get_path()
            if file_path:
                self.window.open_book(file_path)

    def on_preferences_activate(self, action, param):
        """Show preferences dialog"""
        if self.window:
            self.window.show_preferences()

    def on_about_activate(self, action, param):
        """Show about dialog"""
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name=_("Folio"),
            application_icon="se.danielnylander.folio",
            developer_name="Daniel Nylander",
            version="1.0.0",
            website="https://github.com/yeager/folio",
            issue_url="https://github.com/yeager/folio/issues",
            copyright="© 2024 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            developers=["Daniel Nylander https://danielnylander.se"],
            translator_credits=_("translator-credits")
        )
        about.present()

    def on_quit_activate(self, action, param):
        """Quit the application"""
        self.quit()

    def on_open_activate(self, action, param):
        """Open file dialog"""
        if self.window:
            self.window.show_open_dialog()