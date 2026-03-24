"""
Main window for Folio
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib, GdkPixbuf
import os
import gettext

try:
    from .library import LibraryView
    from .reader import ReaderView
    from .utils import is_supported_format
except ImportError:
    # When running from source
    from library import LibraryView
    from reader import ReaderView
    from utils import is_supported_format

_ = gettext.gettext


class BookReaderWindow(Adw.ApplicationWindow):
    """Main application window"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.application = kwargs.get('application')
        self.settings = self.application.settings
        
        self.setup_ui()
        self.setup_actions()
        self.restore_window_state()
    
    def setup_ui(self):
        """Set up the user interface"""
        self.set_title(_("Folio"))
        self.set_icon_name("se.danielnylander.folio")
        self.set_default_size(1200, 800)
        
        # Header bar
        self.header_bar = Adw.HeaderBar()
        
        # Main menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text(_("Main menu"))
        
        # Create main menu
        menu_model = Gio.Menu()
        menu_model.append(_("Preferences"), "app.preferences")
        menu_model.append(_("About"), "app.about")
        menu_model.append(_("Quit"), "app.quit")
        menu_button.set_menu_model(menu_model)
        
        self.header_bar.pack_end(menu_button)
        
        # Main content stack
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        
        # Library view
        self.library_view = LibraryView(self.settings)
        self.library_view.connect('book-selected', self.on_book_selected)
        self.library_view.connect('book-activated', self.on_book_activated)
        self.main_stack.add_named(self.library_view, "library")
        
        # Reader view
        self.reader_view = ReaderView(self.settings)
        self.reader_view.connect('back-requested', self.on_back_to_library)
        self.reader_view.connect('position-changed', self.on_reading_position_changed)
        self.main_stack.add_named(self.reader_view, "reader")
        
        # Show library by default
        self.main_stack.set_visible_child_name("library")
        
        # Toast overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(self.main_stack)
        
        # Use Adw toolbarview for proper layout
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(self.header_bar)
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)
        
        # Connect window signals
        self.connect('close-request', self.on_close_request)
    
    def setup_actions(self):
        """Set up window actions"""
        # Full screen toggle
        fullscreen_action = Gio.SimpleAction.new_stateful(
            "fullscreen", None, GLib.Variant.new_boolean(False)
        )
        fullscreen_action.connect("activate", self.on_fullscreen_activate)
        self.add_action(fullscreen_action)
        
        # Keyboard shortcuts
        self.application.set_accels_for_action("win.fullscreen", ["F11"])
    
    def restore_window_state(self):
        """Restore window state from settings"""
        # Window size
        width = self.settings.get("window_width", 1200)
        height = self.settings.get("window_height", 800)
        self.set_default_size(width, height)
        
        # Maximized state
        if self.settings.get("window_maximized", False):
            self.maximize()
        
        # Load last book if any
        last_book = self.settings.get("last_book", "")
        if last_book and os.path.exists(last_book):
            # Small delay to ensure UI is ready
            GLib.timeout_add(100, lambda: self.open_book(last_book))
    
    def save_window_state(self):
        """Save window state to settings"""
        if not self.is_maximized():
            width, height = self.get_default_size()
            self.settings.set("window_width", width)
            self.settings.set("window_height", height)
        
        self.settings.set("window_maximized", self.is_maximized())
        
        # Save current book
        current_book = self.reader_view.get_current_book_path()
        if current_book:
            self.settings.set("last_book", current_book)
    
    def on_close_request(self, window):
        """Handle window close request"""
        self.save_window_state()
        return False  # Allow close
    
    def on_fullscreen_activate(self, action, param):
        """Toggle fullscreen mode"""
        state = action.get_state().get_boolean()
        action.set_state(GLib.Variant.new_boolean(not state))
        
        if not state:
            self.fullscreen()
        else:
            self.unfullscreen()
    
    def on_book_selected(self, library_view, book_path):
        """Handle book selection from library"""
        if book_path == "ADD_BOOKS":
            self.show_open_dialog()
        else:
            # Just selection, don't open yet
            pass
    
    def on_book_activated(self, library_view, book_path):
        """Handle book activation (double-click) from library"""
        self.open_book(book_path)
    
    def on_back_to_library(self, reader_view):
        """Return to library view"""
        self.main_stack.set_visible_child_name("library")
        self.library_view.refresh_library()
    
    def on_reading_position_changed(self, reader_view, position):
        """Handle reading position change"""
        # Position is automatically saved by reader view
        pass
    
    def open_book(self, file_path):
        """Open a book for reading"""
        if not os.path.exists(file_path):
            self.show_toast(_("File not found: {}").format(file_path))
            return
        
        if not is_supported_format(file_path):
            self.show_toast(_("Unsupported file format"))
            return
        
        try:
            self.reader_view.load_book(file_path)
            self.main_stack.set_visible_child_name("reader")
            self.show_toast(_("Opened: {}").format(os.path.basename(file_path)))
        except Exception as e:
            self.show_toast(_("Error opening book: {}").format(str(e)))
    
    def show_open_dialog(self):
        """Show file open dialog"""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Open Book"))
        
        # Set up file filters
        filters = Gio.ListStore.new(Gtk.FileFilter)
        
        # All supported formats
        all_filter = Gtk.FileFilter()
        all_filter.set_name(_("All supported formats"))
        all_filter.add_pattern("*.epub")
        all_filter.add_pattern("*.pdf")
        all_filter.add_pattern("*.mobi")
        all_filter.add_pattern("*.azw")
        all_filter.add_pattern("*.azw3")
        all_filter.add_pattern("*.fb2")
        all_filter.add_pattern("*.cbz")
        all_filter.add_pattern("*.cbr")
        all_filter.add_pattern("*.txt")
        all_filter.add_pattern("*.html")
        all_filter.add_pattern("*.htm")
        filters.append(all_filter)
        
        # EPUB
        epub_filter = Gtk.FileFilter()
        epub_filter.set_name(_("EPUB e-books (*.epub)"))
        epub_filter.add_pattern("*.epub")
        filters.append(epub_filter)
        
        # PDF
        pdf_filter = Gtk.FileFilter()
        pdf_filter.set_name(_("PDF documents (*.pdf)"))
        pdf_filter.add_pattern("*.pdf")
        filters.append(pdf_filter)
        
        # Comics
        comic_filter = Gtk.FileFilter()
        comic_filter.set_name(_("Comic books (*.cbz, *.cbr)"))
        comic_filter.add_pattern("*.cbz")
        comic_filter.add_pattern("*.cbr")
        filters.append(comic_filter)
        
        # All files
        all_files_filter = Gtk.FileFilter()
        all_files_filter.set_name(_("All files"))
        all_files_filter.add_pattern("*")
        filters.append(all_files_filter)
        
        dialog.set_filters(filters)
        dialog.set_default_filter(all_filter)
        
        # Set initial folder to library path
        library_path = self.settings.get("library_path", 
                                        os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS), "Books"))
        if os.path.exists(library_path):
            dialog.set_initial_folder(Gio.File.new_for_path(library_path))
        
        # Show dialog
        dialog.open(self, None, self.on_open_dialog_response)
    
    def on_open_dialog_response(self, dialog, result):
        """Handle file open dialog response"""
        try:
            file = dialog.open_finish(result)
            if file:
                file_path = file.get_path()
                self.open_book(file_path)
        except Exception as e:
            # User cancelled or error
            pass
    
    def show_preferences(self):
        """Show preferences dialog"""
        dialog = Adw.PreferencesWindow(title=_("Preferences"),
                                     transient_for=self)
        
        # General page
        general_page = Adw.PreferencesPage(title=_("General"))
        dialog.add(general_page)
        
        # Library group
        library_group = Adw.PreferencesGroup(title=_("Library"))
        general_page.add(library_group)
        
        # Library path row
        library_row = Adw.ActionRow(title=_("Library folder"),
                                   subtitle=_("Where your books are stored"))
        
        library_button = Gtk.Button(label=_("Choose Folder"))
        library_button.set_valign(Gtk.Align.CENTER)
        library_button.connect('clicked', self.on_choose_library_folder)
        library_row.add_suffix(library_button)
        
        current_path = self.settings.get("library_path", "")
        if current_path:
            library_row.set_subtitle(current_path)
        
        library_group.add(library_row)
        
        # Appearance group
        appearance_group = Adw.PreferencesGroup(title=_("Appearance"))
        general_page.add(appearance_group)
        
        # Theme row
        theme_row = Adw.ComboRow(title=_("Theme"))
        theme_model = Gtk.StringList()
        themes = [_("System"), _("Light"), _("Dark")]
        for theme in themes:
            theme_model.append(theme)
        theme_row.set_model(theme_model)
        
        current_theme = self.settings.get("theme", "system")
        theme_index = {"system": 0, "light": 1, "dark": 2}.get(current_theme, 0)
        theme_row.set_selected(theme_index)
        
        def on_theme_changed(row, param):
            themes_map = {0: "system", 1: "light", 2: "dark"}
            selected_theme = themes_map[row.get_selected()]
            self.settings.set("theme", selected_theme)
            self.apply_theme(selected_theme)
        
        theme_row.connect('notify::selected', on_theme_changed)
        appearance_group.add(theme_row)
        
        # Font size row
        font_row = Adw.SpinRow.new_with_range(8, 32, 1)
        font_row.set_title(_("Default font size"))
        font_row.set_value(self.settings.get("font_size", 14))
        
        def on_font_size_changed(row, param):
            self.settings.set("font_size", int(row.get_value()))
        
        font_row.connect('notify::value', on_font_size_changed)
        appearance_group.add(font_row)
        
        dialog.present()
    
    def on_choose_library_folder(self, button):
        """Choose library folder"""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Choose Library Folder"))
        
        current_path = self.settings.get("library_path", "")
        if current_path and os.path.exists(current_path):
            dialog.set_initial_folder(Gio.File.new_for_path(current_path))
        
        dialog.select_folder(self, None, self.on_library_folder_selected)
    
    def on_library_folder_selected(self, dialog, result):
        """Handle library folder selection"""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                folder_path = folder.get_path()
                self.settings.set("library_path", folder_path)
                self.show_toast(_("Library folder updated"))
                self.library_view.refresh_library()
        except Exception as e:
            # User cancelled or error
            pass
    
    def apply_theme(self, theme):
        """Apply theme setting"""
        style_manager = Adw.StyleManager.get_default()
        
        if theme == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:  # system
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
    
    def show_toast(self, message):
        """Show a toast notification"""
        toast = Adw.Toast(title=message)
        self.toast_overlay.add_toast(toast)