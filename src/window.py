"""
Main window for Folio
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib, GdkPixbuf, Gdk
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
        self.setup_accessibility()
        self.restore_window_state()
        
        # Apply initial theme
        current_theme = self.settings.get("theme", "system")
        self.apply_theme(current_theme)
    
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
        menu_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Main menu")])
        menu_button.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        
        # Create main menu
        menu_model = Gio.Menu()
        menu_model.append(_("Preferences"), "app.preferences")
        menu_model.append(_("Keyboard Shortcuts"), "app.shortcuts")
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
        
        # Set up drag and drop for file import
        self.setup_drag_drop()
        
        # Reader view
        self.reader_view = ReaderView(self.settings)
        self.reader_view.connect('back-requested', self.on_back_to_library)
        self.reader_view.connect('position-changed', self.on_reading_position_changed)
        self.main_stack.add_named(self.reader_view, "reader")
        
        # Welcome screen
        self.welcome_view = self.create_welcome_screen()
        self.main_stack.add_named(self.welcome_view, "welcome")
        
        # Show appropriate view by default
        self.show_initial_view()
        
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
        
        # Search action
        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", self.on_search_activate)
        self.add_action(search_action)
        
        # Navigation actions
        back_action = Gio.SimpleAction.new("back", None)
        back_action.connect("activate", self.on_back_activate)
        self.add_action(back_action)
        
        prev_page_action = Gio.SimpleAction.new("prev-page", None)
        prev_page_action.connect("activate", self.on_prev_page_activate)
        self.add_action(prev_page_action)
        
        next_page_action = Gio.SimpleAction.new("next-page", None)
        next_page_action.connect("activate", self.on_next_page_activate)
        self.add_action(next_page_action)
        
        first_page_action = Gio.SimpleAction.new("first-page", None)
        first_page_action.connect("activate", self.on_first_page_activate)
        self.add_action(first_page_action)
        
        last_page_action = Gio.SimpleAction.new("last-page", None)
        last_page_action.connect("activate", self.on_last_page_activate)
        self.add_action(last_page_action)
        
        # Font size actions
        font_increase_action = Gio.SimpleAction.new("font-increase", None)
        font_increase_action.connect("activate", self.on_font_increase_activate)
        self.add_action(font_increase_action)
        
        font_decrease_action = Gio.SimpleAction.new("font-decrease", None)
        font_decrease_action.connect("activate", self.on_font_decrease_activate)
        self.add_action(font_decrease_action)
        
        # TTS action
        tts_toggle_action = Gio.SimpleAction.new("tts-toggle", None)
        tts_toggle_action.connect("activate", self.on_tts_toggle_activate)
        self.add_action(tts_toggle_action)
        
        # Keyboard shortcuts
        self.application.set_accels_for_action("win.fullscreen", ["F11"])
        self.application.set_accels_for_action("win.search", ["<Ctrl>f"])
        self.application.set_accels_for_action("win.back", ["Escape"])
        self.application.set_accels_for_action("win.prev-page", ["Left"])
        self.application.set_accels_for_action("win.next-page", ["Right"])
        self.application.set_accels_for_action("win.first-page", ["Home"])
        self.application.set_accels_for_action("win.last-page", ["End"])
        self.application.set_accels_for_action("win.font-increase", ["plus", "KP_Add"])
        self.application.set_accels_for_action("win.font-decrease", ["minus", "KP_Subtract"])
        self.application.set_accels_for_action("win.tts-toggle", ["space"])
    
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
        # Hide welcome screen after opening a book
        if self.main_stack.get_visible_child_name() == "welcome":
            self.main_stack.set_visible_child_name("reader")
    
    def on_back_to_library(self, reader_view):
        """Return to library view"""
        # Show welcome screen if library is empty and setting is enabled
        library_path = self.settings.get("library_path", "")
        library_empty = True
        if library_path and os.path.exists(library_path):
            try:
                files = os.listdir(library_path)
                library_empty = not any(is_supported_format(os.path.join(library_path, f)) 
                                      for f in files if os.path.isfile(os.path.join(library_path, f)))
            except:
                library_empty = True
        
        show_welcome = self.settings.get("show_welcome_screen", True)
        if show_welcome and library_empty:
            self.main_stack.set_visible_child_name("welcome")
        else:
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
            
            # Add to recent files
            if self.application:
                self.application.add_to_recent(file_path)
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
        theme_row.set_subtitle(_("Choose between light, dark, or system theme"))
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
        
        # Translation section
        translation_group = Adw.PreferencesGroup(title=_("Translation"))
        general_page.add(translation_group)
        
        # Help translate row
        translate_row = Adw.ActionRow(
            title=_("Help translate Folio"),
            subtitle=_("Help translate Folio into your language")
        )
        
        translate_button = Gtk.Button(label=_("Open Transifex"))
        translate_button.set_valign(Gtk.Align.CENTER)
        translate_button.add_css_class("flat")
        translate_button.connect("clicked", lambda btn: self.open_url("https://www.transifex.com/danielnylander/folio/"))
        translate_row.add_suffix(translate_button)
        
        translation_group.add(translate_row)
        
        dialog.present()
    
    def open_url(self, url):
        """Open URL in default browser"""
        try:
            Gtk.show_uri(self, url, Gdk.CURRENT_TIME)
        except:
            pass  # Fail silently if can't open URL
    
    def setup_drag_drop(self):
        """Set up drag and drop for file import"""
        # Create drop target for file URIs
        drop_target = Gtk.DropTarget()
        drop_target.set_gtypes([Gio.File])
        drop_target.set_actions(Gdk.DragAction.COPY)
        
        drop_target.connect("drop", self.on_drop)
        drop_target.connect("enter", self.on_drag_enter)
        drop_target.connect("leave", self.on_drag_leave)
        
        self.library_view.add_controller(drop_target)
    
    def on_drag_enter(self, drop_target, x, y):
        """Handle drag enter"""
        self.show_toast(_("Drop files to import"))
        return Gdk.DragAction.COPY
    
    def on_drag_leave(self, drop_target):
        """Handle drag leave"""
        pass
    
    def on_drop(self, drop_target, value, x, y):
        """Handle file drop"""
        if isinstance(value, Gio.File):
            file_path = value.get_path()
            if file_path and is_supported_format(file_path):
                # Copy file to library directory if not already there
                library_path = self.settings.get("library_path", "")
                if library_path and os.path.exists(library_path):
                    import shutil
                    filename = os.path.basename(file_path)
                    target_path = os.path.join(library_path, filename)
                    
                    try:
                        if not os.path.samefile(file_path, target_path):
                            shutil.copy2(file_path, target_path)
                            self.show_toast(_("Imported: {}").format(filename))
                        else:
                            self.show_toast(_("Book already in library"))
                        self.library_view.refresh_library()
                        return True
                    except Exception as e:
                        self.show_toast(_("Error importing file: {}").format(str(e)))
                else:
                    # No library path set, just open the file
                    self.open_book(file_path)
                    return True
            else:
                self.show_toast(_("Unsupported file format"))
        return False
    
    def setup_accessibility(self):
        """Set up accessibility features"""
        # Set window accessible role
        self.set_accessible_role(Gtk.AccessibleRole.WINDOW)
        
        # Monitor style manager for high contrast and text scaling
        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::high-contrast", self.on_high_contrast_changed)
        
        # Apply initial high contrast if enabled
        self.on_high_contrast_changed(style_manager, None)
        
        # Set up text scaling
        if hasattr(style_manager, "get_system_font_options"):
            # Monitor font scaling changes
            style_manager.connect("notify", self.on_system_settings_changed)
    
    def on_high_contrast_changed(self, style_manager, pspec):
        """Handle high contrast theme changes"""
        if style_manager.get_high_contrast():
            # Apply high contrast styles
            self.add_css_class("high-contrast")
        else:
            self.remove_css_class("high-contrast")
    
    def on_system_settings_changed(self, style_manager, pspec):
        """Handle system settings changes like text scaling"""
        # This would be called when system text scaling changes
        # The actual font scaling is handled by GTK automatically
        pass
    
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
    
    def show_shortcuts_window(self):
        """Show keyboard shortcuts window"""
        builder = Gtk.Builder()
        builder.set_translation_domain("folio")
        
        shortcuts_window = Gtk.ShortcutsWindow()
        shortcuts_window.set_transient_for(self)
        
        # Main section
        section = Gtk.ShortcutsSection()
        section.set_title(_("General"))
        section.set_visible(True)
        shortcuts_window.add(section)
        
        # File operations group
        file_group = Gtk.ShortcutsGroup()
        file_group.set_title(_("File Operations"))
        file_group.set_visible(True)
        section.add(file_group)
        
        # Open book shortcut
        open_shortcut = Gtk.ShortcutsShortcut()
        open_shortcut.set_title(_("Open book file"))
        open_shortcut.set_accelerator("<Ctrl>o")
        open_shortcut.set_visible(True)
        file_group.add(open_shortcut)
        
        # Quit shortcut
        quit_shortcut = Gtk.ShortcutsShortcut()
        quit_shortcut.set_title(_("Quit"))
        quit_shortcut.set_accelerator("<Ctrl>q")
        quit_shortcut.set_visible(True)
        file_group.add(quit_shortcut)
        
        # Preferences shortcut
        prefs_shortcut = Gtk.ShortcutsShortcut()
        prefs_shortcut.set_title(_("Preferences"))
        prefs_shortcut.set_accelerator("<Ctrl>comma")
        prefs_shortcut.set_visible(True)
        file_group.add(prefs_shortcut)
        
        # Navigation group
        nav_group = Gtk.ShortcutsGroup()
        nav_group.set_title(_("Navigation"))
        nav_group.set_visible(True)
        section.add(nav_group)
        
        # Search shortcut
        search_shortcut = Gtk.ShortcutsShortcut()
        search_shortcut.set_title(_("Search in book"))
        search_shortcut.set_accelerator("<Ctrl>f")
        search_shortcut.set_visible(True)
        nav_group.add(search_shortcut)
        
        # Back shortcut
        back_shortcut = Gtk.ShortcutsShortcut()
        back_shortcut.set_title(_("Back to library"))
        back_shortcut.set_accelerator("Escape")
        back_shortcut.set_visible(True)
        nav_group.add(back_shortcut)
        
        # Previous/Next page shortcuts
        prev_shortcut = Gtk.ShortcutsShortcut()
        prev_shortcut.set_title(_("Previous page"))
        prev_shortcut.set_accelerator("Left")
        prev_shortcut.set_visible(True)
        nav_group.add(prev_shortcut)
        
        next_shortcut = Gtk.ShortcutsShortcut()
        next_shortcut.set_title(_("Next page"))
        next_shortcut.set_accelerator("Right")
        next_shortcut.set_visible(True)
        nav_group.add(next_shortcut)
        
        # First/Last page shortcuts
        first_shortcut = Gtk.ShortcutsShortcut()
        first_shortcut.set_title(_("First page"))
        first_shortcut.set_accelerator("Home")
        first_shortcut.set_visible(True)
        nav_group.add(first_shortcut)
        
        last_shortcut = Gtk.ShortcutsShortcut()
        last_shortcut.set_title(_("Last page"))
        last_shortcut.set_accelerator("End")
        last_shortcut.set_visible(True)
        nav_group.add(last_shortcut)
        
        # View group
        view_group = Gtk.ShortcutsGroup()
        view_group.set_title(_("View"))
        view_group.set_visible(True)
        section.add(view_group)
        
        # Fullscreen shortcut
        fullscreen_shortcut = Gtk.ShortcutsShortcut()
        fullscreen_shortcut.set_title(_("Toggle fullscreen"))
        fullscreen_shortcut.set_accelerator("F11")
        fullscreen_shortcut.set_visible(True)
        view_group.add(fullscreen_shortcut)
        
        # Font size shortcuts
        font_increase_shortcut = Gtk.ShortcutsShortcut()
        font_increase_shortcut.set_title(_("Increase font size"))
        font_increase_shortcut.set_accelerator("plus")
        font_increase_shortcut.set_visible(True)
        view_group.add(font_increase_shortcut)
        
        font_decrease_shortcut = Gtk.ShortcutsShortcut()
        font_decrease_shortcut.set_title(_("Decrease font size"))
        font_decrease_shortcut.set_accelerator("minus")
        font_decrease_shortcut.set_visible(True)
        view_group.add(font_decrease_shortcut)
        
        # TTS group
        tts_group = Gtk.ShortcutsGroup()
        tts_group.set_title(_("Text-to-Speech"))
        tts_group.set_visible(True)
        section.add(tts_group)
        
        # TTS toggle shortcut
        tts_shortcut = Gtk.ShortcutsShortcut()
        tts_shortcut.set_title(_("Play/Pause TTS"))
        tts_shortcut.set_accelerator("space")
        tts_shortcut.set_visible(True)
        tts_group.add(tts_shortcut)
        
        # Help group
        help_group = Gtk.ShortcutsGroup()
        help_group.set_title(_("Help"))
        help_group.set_visible(True)
        section.add(help_group)
        
        # Shortcuts window shortcut
        shortcuts_shortcut = Gtk.ShortcutsShortcut()
        shortcuts_shortcut.set_title(_("Show keyboard shortcuts"))
        shortcuts_shortcut.set_accelerator("<Ctrl>question")
        shortcuts_shortcut.set_visible(True)
        help_group.add(shortcuts_shortcut)
        
        shortcuts_window.present()
    
    # Action handlers
    def on_search_activate(self, action, param):
        """Handle search action"""
        if self.main_stack.get_visible_child_name() == "reader":
            # Delegate to reader view
            self.reader_view.show_search()
    
    def on_back_activate(self, action, param):
        """Handle back action"""
        if self.main_stack.get_visible_child_name() == "reader":
            self.on_back_to_library(self.reader_view)
    
    def on_prev_page_activate(self, action, param):
        """Handle previous page action"""
        if self.main_stack.get_visible_child_name() == "reader":
            self.reader_view.previous_page()
    
    def on_next_page_activate(self, action, param):
        """Handle next page action"""
        if self.main_stack.get_visible_child_name() == "reader":
            self.reader_view.next_page()
    
    def on_first_page_activate(self, action, param):
        """Handle first page action"""
        if self.main_stack.get_visible_child_name() == "reader":
            self.reader_view.first_page()
    
    def on_last_page_activate(self, action, param):
        """Handle last page action"""
        if self.main_stack.get_visible_child_name() == "reader":
            self.reader_view.last_page()
    
    def on_font_increase_activate(self, action, param):
        """Handle font increase action"""
        if self.main_stack.get_visible_child_name() == "reader":
            current_size = self.settings.get("font_size", 14)
            new_size = min(32, current_size + 1)
            self.settings.set("font_size", new_size)
            self.reader_view.update_font_size(new_size)
    
    def on_font_decrease_activate(self, action, param):
        """Handle font decrease action"""
        if self.main_stack.get_visible_child_name() == "reader":
            current_size = self.settings.get("font_size", 14)
            new_size = max(8, current_size - 1)
            self.settings.set("font_size", new_size)
            self.reader_view.update_font_size(new_size)
    
    def on_tts_toggle_activate(self, action, param):
        """Handle TTS toggle action"""
        if self.main_stack.get_visible_child_name() == "reader":
            self.reader_view.toggle_tts()
    
    def create_welcome_screen(self):
        """Create welcome screen using Adw.StatusPage"""
        welcome_page = Adw.StatusPage()
        welcome_page.set_icon_name("document-open-symbolic")
        welcome_page.set_title(_("Welcome to Folio"))
        welcome_page.set_description(_("Open an e-book to start reading, or add books to your library."))
        
        # Button box for actions
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        
        # Primary action: Open Book
        open_button = Gtk.Button(label=_("Open Book"))
        open_button.add_css_class("suggested-action")
        open_button.add_css_class("pill")
        open_button.set_size_request(200, -1)
        open_button.connect("clicked", lambda btn: self.show_open_dialog())
        button_box.append(open_button)
        
        # Secondary action: Add Books Folder
        folder_button = Gtk.Button(label=_("Add Books Folder"))
        folder_button.add_css_class("pill")
        folder_button.set_size_request(200, -1)
        folder_button.connect("clicked", lambda btn: self.on_choose_library_folder(btn))
        button_box.append(folder_button)
        
        welcome_page.set_child(button_box)
        
        # Create wrapper box for checkbox
        wrapper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        wrapper_box.append(welcome_page)
        
        # "Don't show this again" checkbox at bottom
        checkbox_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        checkbox_box.set_halign(Gtk.Align.CENTER)
        checkbox_box.set_spacing(8)
        
        self.welcome_checkbox = Gtk.CheckButton()
        self.welcome_checkbox.set_label(_("Don't show this again"))
        self.welcome_checkbox.connect("toggled", self.on_welcome_checkbox_toggled)
        
        checkbox_box.append(self.welcome_checkbox)
        wrapper_box.append(checkbox_box)
        
        return wrapper_box
    
    def show_initial_view(self):
        """Determine which view to show initially"""
        # Check if we should show welcome screen
        show_welcome = self.settings.get("show_welcome_screen", True)
        
        # Also check if library is empty
        library_path = self.settings.get("library_path", "")
        library_empty = True
        if library_path and os.path.exists(library_path):
            try:
                files = os.listdir(library_path)
                library_empty = not any(is_supported_format(os.path.join(library_path, f)) 
                                      for f in files if os.path.isfile(os.path.join(library_path, f)))
            except:
                library_empty = True
        
        if show_welcome and library_empty:
            self.main_stack.set_visible_child_name("welcome")
        else:
            self.main_stack.set_visible_child_name("library")
    
    def on_welcome_checkbox_toggled(self, checkbox):
        """Handle welcome checkbox toggle"""
        if checkbox.get_active():
            self.settings.set("show_welcome_screen", False)
        else:
            self.settings.set("show_welcome_screen", True)