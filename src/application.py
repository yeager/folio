"""
Application class for Folio
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib, Gdk
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
            flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        
        self.settings = Settings()
        self.window = None
        self.recent_manager = Gtk.RecentManager.get_default()
        
        # Set up actions
        self.create_actions()

    def create_actions(self):
        """Create application actions"""
        # Preferences action
        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self.on_preferences_activate)
        self.add_action(prefs_action)
        self.set_accels_for_action("app.preferences", ["<Ctrl>comma"])
        
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
        
        # Show keyboard shortcuts action
        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self.on_shortcuts_activate)
        self.add_action(shortcuts_action)
        self.set_accels_for_action("app.shortcuts", ["<Ctrl>question"])

    def do_activate(self):
        """Called when the application is activated"""
        # Load CSS if not already loaded
        if not hasattr(self, 'css_loaded'):
            self.load_css()
            self.css_loaded = True
        
        if not self.window:
            self.window = BookReaderWindow(application=self)
        self.window.present()
    
    def load_css(self):
        """Load application CSS"""
        # Try to find CSS file
        css_paths = [
            "data/style.css",  # When running from source
            "/usr/share/folio/style.css",  # System installation
            os.path.join(os.path.dirname(__file__), "../data/style.css")  # Relative path
        ]
        
        css_provider = Gtk.CssProvider()
        
        for css_path in css_paths:
            if os.path.exists(css_path):
                try:
                    css_provider.load_from_path(css_path)
                    Gtk.StyleContext.add_provider_for_display(
                        Gdk.Display.get_default(),
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
                    print(f"Loaded CSS from: {css_path}")
                    return
                except Exception as e:
                    print(f"Failed to load CSS from {css_path}: {e}")
        
        # Fallback: load CSS from string
        css_content = """
        .sepia-theme { background-color: #F5E6C8; color: #3E2723; }
        .sepia-theme text { background-color: #F5E6C8; color: #3E2723; }
        .night-theme { background-color: #1A1A2E; color: #C8B89A; }
        .night-theme text { background-color: #1A1A2E; color: #C8B89A; }
        """
        
        try:
            css_provider.load_from_data(css_content.encode())
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            print("Loaded fallback CSS")
        except Exception as e:
            print(f"Failed to load fallback CSS: {e}")

    def do_open(self, files, n_files, hint):
        """Called when the application is asked to open files"""
        self.do_activate()
        if files and len(files) > 0:
            # Open the first file
            file_path = files[0].get_path()
            if file_path:
                self.window.open_book(file_path)
                self.add_to_recent(file_path)
    
    def do_command_line(self, command_line):
        """Handle command line arguments"""
        args = command_line.get_arguments()
        
        # Skip the program name
        if len(args) > 1:
            file_path = args[1]
            if os.path.exists(file_path):
                self.do_activate()
                self.window.open_book(file_path)
                self.add_to_recent(file_path)
                return 0
        
        # No file argument, just activate normally
        self.do_activate()
        return 0
    
    def add_to_recent(self, file_path):
        """Add file to recent files"""
        try:
            file_uri = Gio.File.new_for_path(file_path).get_uri()
            self.recent_manager.add_item(file_uri)
        except Exception as e:
            print(f"Failed to add to recent files: {e}")

    def on_preferences_activate(self, action, param):
        """Show preferences dialog"""
        if self.window:
            self.window.show_preferences()

    def on_about_activate(self, action, param):
        """Show about dialog"""
        about = Adw.AboutDialog(
            application_name="Folio",
            application_icon="se.danielnylander.folio",
            version="0.1.0",
            developer_name="Daniel Nylander",
            website="https://github.com/yeager/folio",
            issue_url="https://github.com/yeager/folio/issues",
            license_type=Gtk.License.GPL_3_0,
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            translator_credits=_("translator-credits"),
            copyright="© 2026 Daniel Nylander",
        )
        
        # Add help translate link
        about.add_link(_("Help Translate"), "https://www.transifex.com/danielnylander/folio/")
        
        about.present(self.window)

    def on_quit_activate(self, action, param):
        """Quit the application"""
        self.quit()

    def on_open_activate(self, action, param):
        """Open file dialog"""
        if self.window:
            self.window.show_open_dialog()

    def on_shortcuts_activate(self, action, param):
        """Show keyboard shortcuts window"""
        if self.window:
            self.window.show_shortcuts_window()