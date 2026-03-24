"""
Reader view for Folio
Displays book content with reading controls
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gio, GObject, Pango, GLib
import gettext
import re

try:
    from .book_parser import create_parser
    from .tts import TTSEngine
    from .user_data import UserDataManager
except ImportError:
    # When running from source
    from book_parser import create_parser
    from tts import TTSEngine
    from user_data import UserDataManager

_ = gettext.gettext


class ReaderView(Gtk.Box):
    """Reader view widget"""
    
    __gsignals__ = {
        'back-requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'position-changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }
    
    def __init__(self, settings):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.settings = settings
        self.book_metadata = None
        self.current_chapter = 0
        self.current_book_path = None
        self.reading_session_index = None
        
        # User data manager
        self.user_data = UserDataManager()
        
        # TTS engine
        self.tts_engine = TTSEngine()
        self.tts_engine.connect('word-started', self.on_word_started)
        self.tts_engine.connect('word-finished', self.on_word_finished)
        self.tts_engine.connect('speech-finished', self.on_speech_finished)
        self.tts_engine.connect('speech-error', self.on_speech_error)
        
        # UI state
        self.fullscreen_mode = False
        self.search_bar_visible = False
        self.current_search_results = []
        self.current_search_index = 0
        
        self.setup_ui()
        self.setup_keyboard_shortcuts()
    
    def setup_ui(self):
        """Set up the reader UI"""
        # Sidebar with tabs
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar.set_size_request(280, -1)
        
        # Sidebar tab switcher
        self.sidebar_stack = Gtk.Stack()
        self.sidebar_switcher = Gtk.StackSwitcher()
        self.sidebar_switcher.set_stack(self.sidebar_stack)
        self.sidebar_switcher.set_margin_start(6)
        self.sidebar_switcher.set_margin_end(6)
        self.sidebar_switcher.set_margin_top(6)
        self.sidebar_switcher.set_margin_bottom(6)
        self.sidebar.append(self.sidebar_switcher)
        
        # Table of Contents tab
        toc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled_toc = Gtk.ScrolledWindow()
        scrolled_toc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.toc_list = Gtk.ListBox()
        self.toc_list.add_css_class("navigation-sidebar")
        self.toc_list.connect('row-selected', self.on_chapter_selected)
        scrolled_toc.set_child(self.toc_list)
        toc_box.append(scrolled_toc)
        self.sidebar_stack.add_titled(toc_box, "toc", _("Contents"))
        
        # Bookmarks tab
        bookmarks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bookmarks_box.set_margin_start(6)
        bookmarks_box.set_margin_end(6)
        
        # Bookmark button
        add_bookmark_btn = Gtk.Button(label=_("Add Bookmark"))
        add_bookmark_btn.set_icon_name("bookmark-new-symbolic")
        add_bookmark_btn.connect('clicked', self.on_add_bookmark)
        bookmarks_box.append(add_bookmark_btn)
        
        # Bookmarks list
        scrolled_bookmarks = Gtk.ScrolledWindow()
        scrolled_bookmarks.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.bookmarks_list = Gtk.ListBox()
        self.bookmarks_list.add_css_class("navigation-sidebar")
        self.bookmarks_list.connect('row-selected', self.on_bookmark_selected)
        scrolled_bookmarks.set_child(self.bookmarks_list)
        bookmarks_box.append(scrolled_bookmarks)
        self.sidebar_stack.add_titled(bookmarks_box, "bookmarks", _("Bookmarks"))
        
        # Annotations tab
        annotations_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        annotations_box.set_margin_start(6)
        annotations_box.set_margin_end(6)
        
        # Export button
        export_annotations_btn = Gtk.Button(label=_("Export"))
        export_annotations_btn.set_icon_name("document-save-symbolic")
        export_annotations_btn.connect('clicked', self.on_export_annotations)
        annotations_box.append(export_annotations_btn)
        
        # Annotations list
        scrolled_annotations = Gtk.ScrolledWindow()
        scrolled_annotations.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.annotations_list = Gtk.ListBox()
        self.annotations_list.add_css_class("navigation-sidebar")
        self.annotations_list.connect('row-selected', self.on_annotation_selected)
        scrolled_annotations.set_child(self.annotations_list)
        annotations_box.append(scrolled_annotations)
        self.sidebar_stack.add_titled(annotations_box, "annotations", _("Highlights"))
        
        self.sidebar.append(self.sidebar_stack)
        self.append(self.sidebar)
        
        # Main reading area
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_hexpand(True)
        
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.add_css_class("toolbar")
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        
        # Back button
        back_button = Gtk.Button()
        back_button.set_icon_name("go-previous-symbolic")
        back_button.set_tooltip_text(_("Back to library"))
        back_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Back to library")])
        back_button.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        back_button.connect('clicked', lambda b: self.emit('back-requested'))
        toolbar.append(back_button)
        
        # Book title
        self.book_title_label = Gtk.Label()
        self.book_title_label.add_css_class("heading")
        self.book_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.book_title_label.set_hexpand(True)
        self.book_title_label.set_halign(Gtk.Align.CENTER)
        toolbar.append(self.book_title_label)
        
        # TTS controls
        tts_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        tts_box.add_css_class("linked")
        tts_box.set_accessible_role(Gtk.AccessibleRole.GROUP)
        tts_box.update_property([Gtk.AccessibleProperty.LABEL], [_("Text-to-Speech Controls")])
        
        self.play_button = Gtk.Button()
        self.play_button.set_icon_name("media-playback-start-symbolic")
        self.play_button.set_tooltip_text(_("Play/Pause"))
        self.play_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Play/Pause")])
        self.play_button.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.play_button.connect('clicked', self.on_tts_play_pause)
        tts_box.append(self.play_button)
        
        self.stop_button = Gtk.Button()
        self.stop_button.set_icon_name("media-playback-stop-symbolic")
        self.stop_button.set_tooltip_text(_("Stop"))
        self.stop_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Stop")])
        self.stop_button.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.stop_button.connect('clicked', self.on_tts_stop)
        tts_box.append(self.stop_button)
        
        # Speed control (quick access)
        self.speed_button = Gtk.Button()
        self.speed_button.set_icon_name("multimedia-player-symbolic")
        self.speed_button.set_tooltip_text(_("Speech speed"))
        self.speed_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Speech speed")])
        self.speed_button.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.speed_button.connect('clicked', self.on_speed_clicked)
        tts_box.append(self.speed_button)
        
        toolbar.append(tts_box)
        
        # Search button
        search_button = Gtk.Button()
        search_button.set_icon_name("edit-find-symbolic")
        search_button.set_tooltip_text(_("Search in book (Ctrl+F)"))
        search_button.connect('clicked', self.on_search_clicked)
        toolbar.append(search_button)
        
        # Bookmark button
        bookmark_button = Gtk.Button()
        bookmark_button.set_icon_name("bookmark-new-symbolic")
        bookmark_button.set_tooltip_text(_("Add bookmark (Ctrl+B)"))
        bookmark_button.connect('clicked', self.on_add_bookmark)
        toolbar.append(bookmark_button)
        
        # Settings button
        settings_button = Gtk.MenuButton()
        settings_button.set_icon_name("open-menu-symbolic")
        settings_button.set_tooltip_text(_("Reading settings"))
        
        # Settings menu
        settings_menu = Gio.Menu()
        settings_menu.append(_("Font size..."), "reader.font-size")
        settings_menu.append(_("Reading theme..."), "reader.theme")
        settings_menu.append(_("Line spacing..."), "reader.line-spacing")
        settings_menu.append(_("TTS settings..."), "reader.tts-settings")
        settings_menu.append(_("Dictionary..."), "reader.dictionary")
        settings_menu.append(_("Statistics..."), "reader.statistics")
        settings_button.set_menu_model(settings_menu)
        
        toolbar.append(settings_button)
        
        main_box.append(toolbar)
        
        # Search bar (initially hidden)
        self.search_bar = Gtk.SearchBar()
        search_entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text(_("Search in book..."))
        self.search_entry.connect('search-changed', self.on_search_changed)
        self.search_entry.connect('activate', self.on_search_next)
        search_entry_box.append(self.search_entry)
        
        # Search navigation
        search_prev_btn = Gtk.Button()
        search_prev_btn.set_icon_name("go-up-symbolic")
        search_prev_btn.set_tooltip_text(_("Previous match (Shift+Enter)"))
        search_prev_btn.connect('clicked', self.on_search_prev)
        search_entry_box.append(search_prev_btn)
        
        search_next_btn = Gtk.Button()
        search_next_btn.set_icon_name("go-down-symbolic")
        search_next_btn.set_tooltip_text(_("Next match (Enter)"))
        search_next_btn.connect('clicked', self.on_search_next)
        search_entry_box.append(search_next_btn)
        
        self.search_info_label = Gtk.Label()
        self.search_info_label.set_margin_start(12)
        search_entry_box.append(self.search_info_label)
        
        self.search_bar.set_child(search_entry_box)
        main_box.append(self.search_bar)
        
        # Reading area
        scrolled_content = Gtk.ScrolledWindow()
        scrolled_content.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_content.set_vexpand(True)
        
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_margin_start(24)
        self.text_view.set_margin_end(24)
        self.text_view.set_margin_top(12)
        self.text_view.set_margin_bottom(12)
        
        # Add context menu for text selection
        gesture_secondary = Gtk.GestureClick.new()
        gesture_secondary.set_button(3)  # Right click
        gesture_secondary.connect('pressed', self.on_text_right_click)
        self.text_view.add_controller(gesture_secondary)
        
        # Double-click for dictionary lookup
        gesture_primary = Gtk.GestureClick.new()
        gesture_primary.connect('pressed', self.on_text_clicked)
        self.text_view.add_controller(gesture_primary)
        
        # Set up text formatting
        self.text_buffer = self.text_view.get_buffer()
        self.setup_text_formatting()
        
        scrolled_content.set_child(self.text_view)
        main_box.append(scrolled_content)
        
        # Navigation bar
        nav_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav_bar.set_margin_start(12)
        nav_bar.set_margin_end(12)
        nav_bar.set_margin_bottom(12)
        
        # Previous chapter
        self.prev_button = Gtk.Button()
        self.prev_button.set_icon_name("go-previous-symbolic")
        self.prev_button.set_tooltip_text(_("Previous chapter"))
        self.prev_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Previous chapter")])
        self.prev_button.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.prev_button.connect('clicked', self.on_prev_chapter)
        nav_bar.append(self.prev_button)
        
        # Chapter info
        self.chapter_info = Gtk.Label()
        self.chapter_info.set_hexpand(True)
        self.chapter_info.set_halign(Gtk.Align.CENTER)
        nav_bar.append(self.chapter_info)
        
        # Next chapter
        self.next_button = Gtk.Button()
        self.next_button.set_icon_name("go-next-symbolic")
        self.next_button.set_tooltip_text(_("Next chapter"))
        self.next_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Next chapter")])
        self.next_button.set_accessible_role(Gtk.AccessibleRole.BUTTON)
        self.next_button.connect('clicked', self.on_next_chapter)
        nav_bar.append(self.next_button)
        
        main_box.append(nav_bar)
        
        self.append(main_box)
        
        # Create actions
        self.create_actions()
    
    def setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts"""
        # Create event controller for keyboard
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self.on_key_pressed)
        self.add_controller(key_controller)
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses"""
        ctrl = bool(state & Gtk.Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gtk.Gdk.ModifierType.SHIFT_MASK)
        
        key_name = Gtk.Gdk.keyval_name(keyval)
        
        # Ctrl+F: Search
        if ctrl and key_name == 'f':
            self.on_search_clicked()
            return True
        
        # Ctrl+B: Bookmark
        if ctrl and key_name == 'b':
            self.on_add_bookmark()
            return True
        
        # F11: Fullscreen
        if key_name == 'F11':
            self.toggle_fullscreen()
            return True
        
        # Escape: Exit fullscreen or close search
        if key_name == 'Escape':
            if self.fullscreen_mode:
                self.toggle_fullscreen()
                return True
            elif self.search_bar_visible:
                self.hide_search_bar()
                return True
        
        # Enter/Shift+Enter in search
        if self.search_bar_visible and key_name in ['Return', 'KP_Enter']:
            if shift:
                self.on_search_prev()
            else:
                self.on_search_next()
            return True
        
        return False
    
    def create_actions(self):
        """Create reader actions"""
        # Font size action
        font_action = Gio.SimpleAction.new("font-size", None)
        font_action.connect("activate", self.on_font_size_action)
        
        # Theme action
        theme_action = Gio.SimpleAction.new("theme", None)
        theme_action.connect("activate", self.on_theme_action)
        
        # Line spacing action
        line_spacing_action = Gio.SimpleAction.new("line-spacing", None)
        line_spacing_action.connect("activate", self.on_line_spacing_action)
        
        # TTS settings action
        tts_action = Gio.SimpleAction.new("tts-settings", None)
        tts_action.connect("activate", self.on_tts_settings_action)
        
        # Dictionary action
        dict_action = Gio.SimpleAction.new("dictionary", None)
        dict_action.connect("activate", self.on_dictionary_action)
        
        # Statistics action
        stats_action = Gio.SimpleAction.new("statistics", None)
        stats_action.connect("activate", self.on_statistics_action)
        
        # Add actions to action group
        action_group = Gio.SimpleActionGroup()
        action_group.add_action(font_action)
        action_group.add_action(theme_action)
        action_group.add_action(line_spacing_action)
        action_group.add_action(tts_action)
        action_group.add_action(dict_action)
        action_group.add_action(stats_action)
        self.insert_action_group("reader", action_group)
    
    def setup_text_formatting(self):
        """Set up text buffer formatting"""
        # Create text tags
        tag_table = self.text_buffer.get_tag_table()
        
        # Normal text
        self.normal_tag = Gtk.TextTag.new("normal")
        font_size = self.settings.get("font_size", 14)
        self.normal_tag.props.font = f"serif {font_size}"
        self.normal_tag.props.pixels_below_lines = 5
        tag_table.add(self.normal_tag)
        
        # Highlighted text (for TTS)
        self.highlight_tag = Gtk.TextTag.new("highlight")
        self.highlight_tag.props.background = "#FFEB3B"  # Material Design yellow
        self.highlight_tag.props.weight = Pango.Weight.BOLD
        self.highlight_tag.props.foreground = "#263238"  # Dark text for contrast
        tag_table.add(self.highlight_tag)
        
        # Word boundaries and positions
        self.current_words = []
        self.current_word_positions = []
        self.current_highlighted_word = -1
        
        # Chapter title
        self.title_tag = Gtk.TextTag.new("title")
        self.title_tag.props.font = f"sans bold {font_size + 4}"
        self.title_tag.props.pixels_above_lines = 20
        self.title_tag.props.pixels_below_lines = 15
        tag_table.add(self.title_tag)
    
    def load_book(self, file_path):
        """Load a book for reading"""
        self.current_book_path = file_path
        
        try:
            # Parse the book
            parser = create_parser(file_path)
            self.book_metadata = parser.parse()
            
            # Update UI
            self.book_title_label.set_text(self.book_metadata.title)
            
            # Populate table of contents
            self.populate_toc()
            
            # Load last reading position
            last_position = self.settings.get_reading_position(file_path)
            if last_position < len(self.book_metadata.chapters):
                self.current_chapter = last_position
            else:
                self.current_chapter = 0
            
            # Display current chapter
            self.display_chapter(self.current_chapter)
            
        except Exception as e:
            self.show_error(f"Error loading book: {e}")
    
    def populate_toc(self):
        """Populate table of contents"""
        # Clear existing items
        while True:
            row = self.toc_list.get_row_at_index(0)
            if row is None:
                break
            self.toc_list.remove(row)
        
        # Add chapters
        for i, (chapter_title, content) in enumerate(self.book_metadata.chapters):
            label = Gtk.Label(label=chapter_title)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_halign(Gtk.Align.START)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            
            row = Gtk.ListBoxRow()
            row.set_child(label)
            row.chapter_index = i
            
            self.toc_list.append(row)
    
    def display_chapter(self, chapter_index):
        """Display a specific chapter"""
        if (not self.book_metadata or 
            chapter_index < 0 or 
            chapter_index >= len(self.book_metadata.chapters)):
            return
        
        chapter_title, content = self.book_metadata.chapters[chapter_index]
        
        # Clear buffer
        self.text_buffer.set_text("")
        
        # Add chapter title
        iter_start = self.text_buffer.get_start_iter()
        self.text_buffer.insert_with_tags(iter_start, f"{chapter_title}\n\n", self.title_tag)
        
        # Add content
        iter_end = self.text_buffer.get_end_iter()
        self.text_buffer.insert_with_tags(iter_end, content, self.normal_tag)
        
        # Store current content for TTS and other features
        self.current_content = content
        
        # Build word index for TTS
        self._build_word_index(content)
        
        # Update navigation
        self.update_navigation()
        
        # Select current chapter in TOC
        if 0 <= chapter_index < self.toc_list.get_n_items():
            row = self.toc_list.get_row_at_index(chapter_index)
            self.toc_list.select_row(row)
        
        # Save position
        if self.current_book_path:
            self.settings.set_reading_position(self.current_book_path, chapter_index)
            self.emit('position-changed', chapter_index)
            
    def _build_word_index(self, content):
        """Build index of word positions for TTS highlighting"""
        self.current_words = []
        self.current_word_positions = []
        
        # Split content into words while preserving positions
        import re
        word_pattern = re.compile(r'\S+')
        
        # Find the content start (after title and newlines)
        text = self.text_buffer.get_text(
            self.text_buffer.get_start_iter(),
            self.text_buffer.get_end_iter(),
            False
        )
        
        # Find where content starts (after title)
        title_end = text.find('\n\n')
        if title_end == -1:
            content_start = 0
        else:
            content_start = title_end + 2
            
        # Find words in the content part
        for match in word_pattern.finditer(content):
            word = match.group()
            word_start = match.start()
            word_end = match.end()
            
            # Calculate buffer positions
            buffer_start = content_start + word_start
            buffer_end = content_start + word_end
            
            # Get iterators
            start_iter = self.text_buffer.get_iter_at_offset(buffer_start)
            end_iter = self.text_buffer.get_iter_at_offset(buffer_end)
            
            self.current_words.append(word)
            self.current_word_positions.append((start_iter.copy(), end_iter.copy()))
    
    def highlight_word(self, word_index):
        """Highlight a specific word by index"""
        # Clear previous highlight
        if self.current_highlighted_word >= 0:
            start = self.text_buffer.get_start_iter()
            end = self.text_buffer.get_end_iter()
            self.text_buffer.remove_tag(self.highlight_tag, start, end)
        
        # Highlight current word
        if 0 <= word_index < len(self.current_word_positions):
            start_iter, end_iter = self.current_word_positions[word_index]
            self.text_buffer.apply_tag(self.highlight_tag, start_iter, end_iter)
            
            # Auto-scroll to keep word visible
            mark = self.text_buffer.create_mark(None, start_iter, False)
            self.text_view.scroll_to_mark(mark, 0.25, False, 0.0, 0.5)
            self.text_buffer.delete_mark(mark)
            
            self.current_highlighted_word = word_index
    
    def clear_highlight(self):
        """Clear all highlighting"""
        start = self.text_buffer.get_start_iter()
        end = self.text_buffer.get_end_iter()
        self.text_buffer.remove_tag(self.highlight_tag, start, end)
        self.current_highlighted_word = -1
    
    def update_navigation(self):
        """Update navigation controls"""
        total_chapters = len(self.book_metadata.chapters) if self.book_metadata else 0
        
        self.prev_button.set_sensitive(self.current_chapter > 0)
        self.next_button.set_sensitive(self.current_chapter < total_chapters - 1)
        
        if total_chapters > 0:
            chapter_title = self.book_metadata.chapters[self.current_chapter][0]
            self.chapter_info.set_text(f"{self.current_chapter + 1} / {total_chapters}: {chapter_title}")
        else:
            self.chapter_info.set_text("")
    
    def on_chapter_selected(self, list_box, row):
        """Handle chapter selection from TOC"""
        if row and hasattr(row, 'chapter_index'):
            self.current_chapter = row.chapter_index
            self.display_chapter(self.current_chapter)
    
    def on_prev_chapter(self, button):
        """Go to previous chapter"""
        if self.current_chapter > 0:
            self.current_chapter -= 1
            self.display_chapter(self.current_chapter)
    
    def on_next_chapter(self, button):
        """Go to next chapter"""
        if (self.book_metadata and 
            self.current_chapter < len(self.book_metadata.chapters) - 1):
            self.current_chapter += 1
            self.display_chapter(self.current_chapter)
    
    def on_tts_play_pause(self, button):
        """Handle TTS play/pause"""
        if self.tts_engine.is_speaking():
            if self.tts_engine.is_paused:
                self.tts_engine.resume()
                self.play_button.set_icon_name("media-playback-pause-symbolic")
            else:
                self.tts_engine.pause()
                self.play_button.set_icon_name("media-playbook-start-symbolic")
        else:
            # Start reading current chapter
            if self.book_metadata and self.current_chapter < len(self.book_metadata.chapters):
                chapter_content = self.book_metadata.chapters[self.current_chapter][1]
                
                # Set TTS settings
                voice = self.settings.get("tts_voice", "sv_SE-nst-medium")
                speed = self.settings.get("tts_speed", 1.0)
                self.tts_engine.set_voice(voice)
                self.tts_engine.set_speed(speed)
                
                if self.tts_engine.speak_text(chapter_content, self.current_words):
                    self.play_button.set_icon_name("media-playback-pause-symbolic")
    
    def on_tts_stop(self, button):
        """Handle TTS stop"""
        self.tts_engine.stop()
        self.play_button.set_icon_name("media-playback-start-symbolic")
        
        # Clear highlight
        self.clear_highlight()
        
    def on_speed_clicked(self, button):
        """Quick speed adjustment"""
        current_speed = self.settings.get("tts_speed", 1.0)
        # Cycle through speeds: 0.8x -> 1.0x -> 1.2x -> 1.5x -> 0.8x
        speeds = [0.8, 1.0, 1.2, 1.5]
        
        try:
            current_index = speeds.index(current_speed)
            next_index = (current_index + 1) % len(speeds)
        except ValueError:
            next_index = 0
            
        new_speed = speeds[next_index]
        self.settings.set("tts_speed", new_speed)
        self.tts_engine.set_speed(new_speed)
        
        # Update button tooltip
        self.speed_button.set_tooltip_text(_("Speech speed: {}x").format(new_speed))
    
    def on_word_started(self, engine, word_index):
        """Handle TTS word start"""
        self.highlight_word(word_index)
    
    def on_word_finished(self, engine, word_index):
        """Handle TTS word finish"""
        # Word highlighting continues until next word starts
        pass
    
    def on_speech_finished(self, engine):
        """Handle TTS completion"""
        self.play_button.set_icon_name("media-playback-start-symbolic")
        
        # Clear highlighting
        self.clear_highlight()
        
        # Auto page turn if enabled
        if self.settings.get("auto_page_turn", True):
            auto_advance_delay = 2000  # 2 seconds
            GLib.timeout_add(auto_advance_delay, self.auto_advance_page)
    
    def auto_advance_page(self):
        """Automatically advance to next chapter"""
        if (self.book_metadata and 
            self.current_chapter < len(self.book_metadata.chapters) - 1):
            self.on_next_chapter(None)
        return False  # Don't repeat
    
    def on_speech_error(self, engine, error_message):
        """Handle TTS error"""
        self.play_button.set_icon_name("media-playback-start-symbolic")
        self.clear_highlight()
        self.show_error(f"TTS Error: {error_message}")
    
    def on_font_size_action(self, action, param):
        """Show font size dialog"""
        dialog = Gtk.Dialog(title=_("Font Size"), 
                           transient_for=self.get_root(),
                           modal=True)
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("OK"), Gtk.ResponseType.OK)
        
        content = dialog.get_content_area()
        
        label = Gtk.Label(label=_("Font size:"))
        content.append(label)
        
        adjustment = Gtk.Adjustment(value=self.settings.get("font_size", 14),
                                  lower=8, upper=32, step_increment=1)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, 
                         adjustment=adjustment)
        scale.set_digits(0)
        scale.set_hexpand(True)
        content.append(scale)
        
        dialog.connect('response', self.on_font_size_response, scale)
        dialog.present()
    
    def on_font_size_response(self, dialog, response, scale):
        """Handle font size dialog response"""
        if response == Gtk.ResponseType.OK:
            new_size = int(scale.get_value())
            self.settings.set("font_size", new_size)
            
            # Update text formatting
            self.normal_tag.props.font = f"serif {new_size}"
            self.title_tag.props.font = f"sans bold {new_size + 4}"
            
            # Refresh display
            self.display_chapter(self.current_chapter)
        
        dialog.destroy()
    
    def on_tts_settings_action(self, action, param):
        """Show TTS settings dialog"""
        dialog = Adw.PreferencesWindow(title=_("TTS Settings"),
                                     transient_for=self.get_root())
        
        # Voice settings page
        page = Adw.PreferencesPage(title=_("Voice"))
        dialog.add(page)
        
        # Voice group
        voice_group = Adw.PreferencesGroup(title=_("Voice Selection"))
        page.add(voice_group)
        
        # Voice combo row
        voices = self.tts_engine.get_available_voices()
        voice_row = Adw.ComboRow(title=_("Voice"))
        voice_model = Gtk.StringList()
        for voice in voices:
            voice_model.append(voice)
        voice_row.set_model(voice_model)
        
        current_voice = self.settings.get("tts_voice", "sv_SE-nst-medium")
        try:
            voice_row.set_selected(voices.index(current_voice))
        except ValueError:
            voice_row.set_selected(0)
        
        voice_group.add(voice_row)
        
        # Speed group
        speed_group = Adw.PreferencesGroup(title=_("Speed"))
        page.add(speed_group)
        
        # Speed spin row
        speed_row = Adw.SpinRow.new_with_range(0.5, 2.0, 0.1)
        speed_row.set_title(_("Speech rate"))
        speed_row.set_value(self.settings.get("tts_speed", 1.0))
        speed_group.add(speed_row)
        
        # Auto page turn
        auto_row = Adw.SwitchRow(title=_("Auto page turn"),
                               subtitle=_("Automatically turn to next page after TTS finishes"))
        auto_row.set_active(self.settings.get("auto_page_turn", True))
        speed_group.add(auto_row)
        
        # Connect save action
        def save_tts_settings():
            selected_voice = voices[voice_row.get_selected()]
            self.settings.set("tts_voice", selected_voice)
            self.settings.set("tts_speed", speed_row.get_value())
            self.settings.set("auto_page_turn", auto_row.get_active())
        
        voice_row.connect('notify::selected', lambda *args: save_tts_settings())
        speed_row.connect('notify::value', lambda *args: save_tts_settings())
        auto_row.connect('notify::active', lambda *args: save_tts_settings())
        
        dialog.present()
    
    def show_error(self, message):
        """Show error message"""
        toast = Adw.Toast(title=message)
        # Would need toast overlay in parent window
        print(f"Error: {message}")
    
    def get_current_book_path(self):
        """Get current book file path"""
        return self.current_book_path
    
    def show_search(self):
        """Show search functionality (placeholder for now)"""
        # For now, just show a toast - could be implemented later
        self.show_error(_("Search functionality not yet implemented"))
    
    def previous_page(self):
        """Go to previous page/chapter"""
        if self.current_chapter > 0:
            self.current_chapter -= 1
            self.display_chapter(self.current_chapter)
            self.update_navigation()
    
    def next_page(self):
        """Go to next page/chapter"""
        if self.book_metadata and self.current_chapter < len(self.book_metadata.chapters) - 1:
            self.current_chapter += 1
            self.display_chapter(self.current_chapter)
            self.update_navigation()
    
    def first_page(self):
        """Go to first page/chapter"""
        if self.book_metadata:
            self.current_chapter = 0
            self.display_chapter(self.current_chapter)
            self.update_navigation()
    
    def last_page(self):
        """Go to last page/chapter"""
        if self.book_metadata:
            self.current_chapter = len(self.book_metadata.chapters) - 1
            self.display_chapter(self.current_chapter)
            self.update_navigation()
    
    def update_font_size(self, font_size):
        """Update the font size"""
        if hasattr(self, 'content_label'):
            font_desc = Pango.FontDescription()
            font_desc.set_size(font_size * Pango.SCALE)
            attrs = Pango.AttrList()
            attrs.insert(Pango.AttrFontDesc.new(font_desc))
            self.content_label.set_attributes(attrs)
    
    def toggle_tts(self):
        """Toggle TTS play/pause"""
        if self.tts_engine.is_speaking():
            self.tts_engine.stop()
        else:
            # Start TTS if there's content
            if hasattr(self, 'current_content') and self.current_content:
                self.tts_engine.speak(self.current_content)
    
    # New event handlers
    def on_search_clicked(self, button=None):
        """Show/hide search bar"""
        self.search_bar_visible = not self.search_bar_visible
        self.search_bar.set_search_mode(self.search_bar_visible)
        if self.search_bar_visible:
            self.search_entry.grab_focus()
        else:
            self.text_view.grab_focus()
    
    def hide_search_bar(self):
        """Hide search bar"""
        self.search_bar_visible = False
        self.search_bar.set_search_mode(False)
        self.clear_search_highlights()
        self.text_view.grab_focus()
    
    def on_search_changed(self, entry):
        """Handle search text change"""
        search_text = entry.get_text().strip()
        if len(search_text) >= 2:  # Start searching at 2 characters
            self.perform_search(search_text)
        else:
            self.clear_search_highlights()
            self.search_info_label.set_text("")
    
    def perform_search(self, search_text):
        """Perform search in current chapter"""
        if not self.book_metadata or not search_text:
            return
        
        # Clear previous results
        self.clear_search_highlights()
        self.current_search_results = []
        
        # Get current chapter text
        if self.current_chapter < len(self.book_metadata.chapters):
            chapter_content = self.book_metadata.chapters[self.current_chapter][1]
            
            # Find all matches (case insensitive)
            search_lower = search_text.lower()
            content_lower = chapter_content.lower()
            
            start = 0
            while True:
                pos = content_lower.find(search_lower, start)
                if pos == -1:
                    break
                
                self.current_search_results.append({
                    'start': pos,
                    'end': pos + len(search_text),
                    'chapter': self.current_chapter
                })
                start = pos + 1
        
        # Highlight matches
        self.highlight_search_results()
        self.update_search_info()
        
        # Jump to first result
        if self.current_search_results:
            self.current_search_index = 0
            self.jump_to_search_result(0)
    
    def highlight_search_results(self):
        """Highlight search results in text view"""
        if not hasattr(self, 'search_tag'):
            # Create search highlight tag
            tag_table = self.text_buffer.get_tag_table()
            self.search_tag = Gtk.TextTag.new("search")
            self.search_tag.props.background = "#FF5722"  # Orange background
            self.search_tag.props.foreground = "#FFFFFF"  # White text
            tag_table.add(self.search_tag)
            
            self.search_current_tag = Gtk.TextTag.new("search-current")
            self.search_current_tag.props.background = "#4CAF50"  # Green background
            self.search_current_tag.props.foreground = "#FFFFFF"  # White text
            tag_table.add(self.search_current_tag)
        
        # Apply highlights
        for result in self.current_search_results:
            if result['chapter'] == self.current_chapter:
                start_iter = self.text_buffer.get_iter_at_offset(result['start'])
                end_iter = self.text_buffer.get_iter_at_offset(result['end'])
                self.text_buffer.apply_tag(self.search_tag, start_iter, end_iter)
    
    def clear_search_highlights(self):
        """Clear search highlights"""
        if hasattr(self, 'search_tag'):
            start_iter = self.text_buffer.get_start_iter()
            end_iter = self.text_buffer.get_end_iter()
            self.text_buffer.remove_tag(self.search_tag, start_iter, end_iter)
            self.text_buffer.remove_tag(self.search_current_tag, start_iter, end_iter)
    
    def update_search_info(self):
        """Update search results info"""
        if self.current_search_results:
            total = len(self.current_search_results)
            current = self.current_search_index + 1 if total > 0 else 0
            self.search_info_label.set_text(f"{current}/{total}")
        else:
            self.search_info_label.set_text(_("No matches"))
    
    def jump_to_search_result(self, index):
        """Jump to specific search result"""
        if 0 <= index < len(self.current_search_results):
            result = self.current_search_results[index]
            
            # Switch to correct chapter if needed
            if result['chapter'] != self.current_chapter:
                self.current_chapter = result['chapter']
                self.display_chapter(self.current_chapter)
                # Re-perform search in new chapter
                search_text = self.search_entry.get_text()
                self.perform_search(search_text)
                return
            
            # Scroll to result
            start_iter = self.text_buffer.get_iter_at_offset(result['start'])
            end_iter = self.text_buffer.get_iter_at_offset(result['end'])
            
            # Remove previous current highlight
            if hasattr(self, 'search_current_tag'):
                start = self.text_buffer.get_start_iter()
                end = self.text_buffer.get_end_iter()
                self.text_buffer.remove_tag(self.search_current_tag, start, end)
            
            # Add current highlight
            self.text_buffer.apply_tag(self.search_current_tag, start_iter, end_iter)
            
            # Scroll to result
            self.text_view.scroll_to_iter(start_iter, 0.25, False, 0.0, 0.5)
            
            self.current_search_index = index
            self.update_search_info()
    
    def on_search_next(self, button=None):
        """Go to next search result"""
        if self.current_search_results:
            next_index = (self.current_search_index + 1) % len(self.current_search_results)
            self.jump_to_search_result(next_index)
    
    def on_search_prev(self, button=None):
        """Go to previous search result"""
        if self.current_search_results:
            prev_index = (self.current_search_index - 1) % len(self.current_search_results)
            self.jump_to_search_result(prev_index)
    
    def on_add_bookmark(self, button=None):
        """Add bookmark at current position"""
        if not self.book_metadata or not self.current_book_path:
            return
        
        # Get current position in text
        mark = self.text_buffer.get_insert()
        iter_pos = self.text_buffer.get_iter_at_mark(mark)
        position = iter_pos.get_offset()
        
        # Get preview text around current position
        start_iter = self.text_buffer.get_iter_at_offset(max(0, position - 50))
        end_iter = self.text_buffer.get_iter_at_offset(position + 50)
        preview_text = self.text_buffer.get_text(start_iter, end_iter, False)
        
        # Add bookmark
        if self.user_data.add_bookmark(self.current_book_path, self.current_chapter, 
                                      position, preview_text):
            # Show success feedback
            toast = Adw.Toast(title=_("Bookmark added"))
            self.show_toast(toast)
            self.update_bookmarks_list()
        else:
            # Bookmark already exists
            toast = Adw.Toast(title=_("Bookmark already exists here"))
            self.show_toast(toast)
    
    def on_bookmark_selected(self, listbox, row):
        """Navigate to selected bookmark"""
        if row:
            bookmark_data = row.get_child().bookmark_data
            self.current_chapter = bookmark_data['chapter_index']
            self.display_chapter(self.current_chapter)
            
            # Scroll to bookmark position
            iter_pos = self.text_buffer.get_iter_at_offset(bookmark_data['position'])
            self.text_view.scroll_to_iter(iter_pos, 0.25, False, 0.0, 0.5)
    
    def update_bookmarks_list(self):
        """Update bookmarks list in sidebar"""
        if not self.current_book_path:
            return
        
        # Clear current list
        while True:
            row = self.bookmarks_list.get_row_at_index(0)
            if row:
                self.bookmarks_list.remove(row)
            else:
                break
        
        # Add bookmarks
        bookmarks = self.user_data.get_bookmarks(self.current_book_path)
        for bookmark in bookmarks:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_margin_start(6)
            box.set_margin_end(6)
            box.set_margin_top(3)
            box.set_margin_bottom(3)
            
            # Chapter info
            chapter_label = Gtk.Label()
            chapter_label.set_text(f"Chapter {bookmark['chapter_index'] + 1}")
            chapter_label.set_halign(Gtk.Align.START)
            chapter_label.add_css_class("caption")
            box.append(chapter_label)
            
            # Preview text
            preview_label = Gtk.Label()
            preview_label.set_text(bookmark['preview_text'])
            preview_label.set_ellipsize(Pango.EllipsizeMode.END)
            preview_label.set_lines(2)
            preview_label.set_halign(Gtk.Align.START)
            preview_label.set_wrap(True)
            box.append(preview_label)
            
            row.set_child(box)
            box.bookmark_data = bookmark
            self.bookmarks_list.append(row)
    
    def on_annotation_selected(self, listbox, row):
        """Navigate to selected annotation"""
        if row:
            annotation_data = row.get_child().annotation_data
            self.current_chapter = annotation_data['chapter_index']
            self.display_chapter(self.current_chapter)
            
            # Scroll to annotation position
            start_iter = self.text_buffer.get_iter_at_offset(annotation_data['start_pos'])
            self.text_view.scroll_to_iter(start_iter, 0.25, False, 0.0, 0.5)
    
    def update_annotations_list(self):
        """Update annotations list in sidebar"""
        if not self.current_book_path:
            return
        
        # Clear current list
        while True:
            row = self.annotations_list.get_row_at_index(0)
            if row:
                self.annotations_list.remove(row)
            else:
                break
        
        # Add annotations
        annotations = self.user_data.get_annotations(self.current_book_path)
        for annotation in annotations:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_margin_start(6)
            box.set_margin_end(6)
            box.set_margin_top(3)
            box.set_margin_bottom(3)
            
            # Color indicator
            color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            color_indicator = Gtk.Box()
            color_indicator.set_size_request(12, 12)
            color_indicator.add_css_class("circular")
            color_indicator.set_css_classes([f"highlight-{annotation['color']}"])
            color_box.append(color_indicator)
            
            # Chapter info
            chapter_label = Gtk.Label()
            chapter_label.set_text(f"Ch. {annotation['chapter_index'] + 1}")
            chapter_label.add_css_class("caption")
            color_box.append(chapter_label)
            
            box.append(color_box)
            
            # Text
            text_label = Gtk.Label()
            text_label.set_text(annotation['text'])
            text_label.set_ellipsize(Pango.EllipsizeMode.END)
            text_label.set_lines(2)
            text_label.set_halign(Gtk.Align.START)
            text_label.set_wrap(True)
            box.append(text_label)
            
            # Comment (if any)
            if annotation.get('comment'):
                comment_label = Gtk.Label()
                comment_label.set_text(annotation['comment'])
                comment_label.set_ellipsize(Pango.EllipsizeMode.END)
                comment_label.set_halign(Gtk.Align.START)
                comment_label.add_css_class("dim-label")
                comment_label.add_css_class("caption")
                box.append(comment_label)
            
            row.set_child(box)
            box.annotation_data = annotation
            self.annotations_list.append(row)
    
    def on_export_annotations(self, button):
        """Export annotations as Markdown"""
        if not self.current_book_path:
            return
        
        # Get book title
        book_title = self.book_metadata.title if self.book_metadata else "Unknown Book"
        
        # Export annotations
        markdown_content = self.user_data.export_annotations_markdown(
            self.current_book_path, book_title
        )
        
        if not markdown_content:
            toast = Adw.Toast(title=_("No annotations to export"))
            self.show_toast(toast)
            return
        
        # Save to file
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Export Annotations"))
        dialog.set_initial_name(f"{book_title}_annotations.md")
        
        def on_save_finish(dialog, result):
            try:
                file = dialog.save_finish(result)
                if file:
                    file_path = file.get_path()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    toast = Adw.Toast(title=_("Annotations exported successfully"))
                    self.show_toast(toast)
            except Exception as e:
                toast = Adw.Toast(title=f"Export failed: {e}")
                self.show_toast(toast)
        
        dialog.save(self.get_root(), None, on_save_finish)
    
    def on_text_right_click(self, gesture, n_press, x, y):
        """Handle right-click on text (context menu)"""
        # Check if text is selected
        if self.text_buffer.get_has_selection():
            # Get selected text
            start_iter, end_iter = self.text_buffer.get_selection_bounds()
            selected_text = self.text_buffer.get_text(start_iter, end_iter, False)
            
            # Show context menu for highlighting
            self.show_highlight_menu(selected_text, start_iter, end_iter, x, y)
    
    def show_highlight_menu(self, text, start_iter, end_iter, x, y):
        """Show highlight context menu"""
        menu = Gio.Menu()
        
        # Highlight colors
        colors = [
            ("yellow", _("Yellow highlight")),
            ("green", _("Green highlight")),
            ("blue", _("Blue highlight")),
            ("red", _("Red highlight")),
            ("orange", _("Orange highlight")),
            ("purple", _("Purple highlight"))
        ]
        
        for color, label in colors:
            menu.append(label, f"highlight.{color}")
        
        # Create popover
        popover = Gtk.PopoverMenu()
        popover.set_menu_model(menu)
        
        # Create actions for highlighting
        action_group = Gio.SimpleActionGroup()
        
        def create_highlight_action(color):
            action = Gio.SimpleAction.new(color, None)
            def on_highlight(action, param):
                self.add_highlight(text, start_iter, end_iter, color)
            action.connect('activate', on_highlight)
            return action
        
        for color, _ in colors:
            action_group.add_action(create_highlight_action(color))
        
        popover.insert_action_group("highlight", action_group)
        
        # Position and show
        rect = Gtk.Rectangle()
        rect.x, rect.y = int(x), int(y)
        rect.width = rect.height = 1
        popover.set_pointing_to(rect)
        popover.set_parent(self.text_view)
        popover.popup()
    
    def add_highlight(self, text, start_iter, end_iter, color):
        """Add text highlight/annotation"""
        if not self.current_book_path:
            return
        
        start_pos = start_iter.get_offset()
        end_pos = end_iter.get_offset()
        
        # Add to user data
        self.user_data.add_annotation(
            self.current_book_path, self.current_chapter,
            start_pos, end_pos, text, "highlight", color
        )
        
        # Update annotations list
        self.update_annotations_list()
        
        # Apply visual highlight
        self.apply_annotation_highlights()
        
        toast = Adw.Toast(title=f"{color.title()} highlight added")
        self.show_toast(toast)
    
    def apply_annotation_highlights(self):
        """Apply visual highlights for annotations"""
        if not self.current_book_path:
            return
        
        annotations = self.user_data.get_annotations(self.current_book_path)
        
        for annotation in annotations:
            if annotation['chapter_index'] == self.current_chapter:
                # Create or get highlight tag for this color
                tag_name = f"highlight-{annotation['color']}"
                tag_table = self.text_buffer.get_tag_table()
                tag = tag_table.lookup(tag_name)
                
                if not tag:
                    tag = Gtk.TextTag.new(tag_name)
                    colors = {
                        'yellow': '#FFEB3B',
                        'green': '#4CAF50',
                        'blue': '#2196F3',
                        'red': '#F44336',
                        'orange': '#FF9800',
                        'purple': '#9C27B0'
                    }
                    tag.props.background = colors.get(annotation['color'], '#FFEB3B')
                    tag_table.add(tag)
                
                # Apply highlight
                start_iter = self.text_buffer.get_iter_at_offset(annotation['start_pos'])
                end_iter = self.text_buffer.get_iter_at_offset(annotation['end_pos'])
                self.text_buffer.apply_tag(tag, start_iter, end_iter)
    
    def on_text_clicked(self, gesture, n_press, x, y):
        """Handle text clicks (double-click for dictionary)"""
        if n_press == 2:  # Double-click
            # Get word at position
            buffer_x, buffer_y = self.text_view.window_to_buffer_coords(
                Gtk.TextWindowType.WIDGET, x, y
            )
            iter_pos = self.text_view.get_iter_at_location(buffer_x, buffer_y)
            if iter_pos[0]:
                word = self.get_word_at_iter(iter_pos[1])
                if word:
                    self.show_dictionary_popup(word, x, y)
    
    def get_word_at_iter(self, iter_pos):
        """Get word at text iterator position"""
        # Move to word boundaries
        start_iter = iter_pos.copy()
        end_iter = iter_pos.copy()
        
        # Move to start of word
        while not start_iter.starts_word():
            if not start_iter.backward_char():
                break
        
        # Move to end of word
        while not end_iter.ends_word():
            if not end_iter.forward_char():
                break
        
        word = self.text_buffer.get_text(start_iter, end_iter, False)
        return word.strip()
    
    def show_dictionary_popup(self, word, x, y):
        """Show dictionary definition popup"""
        # Create popover with loading message
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        
        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{word}</b>")
        box.append(title_label)
        
        content_label = Gtk.Label()
        content_label.set_text(_("Looking up definition..."))
        content_label.set_wrap(True)
        content_label.set_max_width_chars(40)
        box.append(content_label)
        
        popover.set_child(box)
        
        # Position and show
        rect = Gtk.Rectangle()
        rect.x, rect.y = int(x), int(y)
        rect.width = rect.height = 1
        popover.set_pointing_to(rect)
        popover.set_parent(self.text_view)
        popover.popup()
        
        # Look up definition asynchronously
        def lookup_definition():
            definition = self.lookup_word_definition(word)
            GLib.idle_add(lambda: self.update_dictionary_popup(content_label, definition))
        
        import threading
        thread = threading.Thread(target=lookup_definition)
        thread.daemon = True
        thread.start()
    
    def lookup_word_definition(self, word):
        """Look up word definition from Wiktionary API"""
        try:
            import urllib.request
            import json
            
            # Try Swedish first, then English
            for lang in ['sv', 'en']:
                url = f"https://{lang}.wiktionary.org/api/rest_v1/page/definition/{word}"
                
                try:
                    req = urllib.request.Request(url)
                    req.add_header('User-Agent', 'Folio/1.0')
                    
                    with urllib.request.urlopen(req, timeout=5) as response:
                        data = json.loads(response.read().decode())
                        
                        if data and lang in data:
                            definitions = []
                            for entry in data[lang][:3]:  # Limit to 3 definitions
                                if 'definitions' in entry:
                                    for definition in entry['definitions'][:2]:
                                        if 'definition' in definition:
                                            definitions.append(definition['definition'])
                            
                            if definitions:
                                return '\n\n'.join(definitions)
                
                except:
                    continue
            
            return _("Definition not found")
        
        except Exception as e:
            return f"Error: {e}"
    
    def update_dictionary_popup(self, label, definition):
        """Update dictionary popup with definition"""
        # Strip HTML tags from definition
        import re
        definition = re.sub(r'<[^>]+>', '', definition)
        
        label.set_text(definition)
        return False
    
    def toggle_fullscreen(self):
        """Toggle fullscreen reading mode"""
        self.fullscreen_mode = not self.fullscreen_mode
        
        # Get main window
        window = self.get_root()
        if window:
            if self.fullscreen_mode:
                window.fullscreen()
                # Hide toolbar and navigation in fullscreen
                # This would need to be implemented in the window class
            else:
                window.unfullscreen()
    
    def show_toast(self, toast):
        """Show toast notification"""
        # This would need to be implemented by the parent window
        # For now, just print the message
        print(f"Toast: {toast.get_title()}")
    
    def on_theme_action(self, action, param):
        """Handle theme change"""
        # Create theme selection dialog
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Reading Theme"))
        dialog.set_body(_("Choose a reading theme"))
        
        # Theme options
        dialog.add_response("default", _("Default"))
        dialog.add_response("sepia", _("Sepia"))
        dialog.add_response("night", _("Night"))
        
        dialog.set_default_response("default")
        
        def on_response(dialog, response):
            self.apply_reading_theme(response)
        
        dialog.connect('response', on_response)
        dialog.present(self.get_root())
    
    def apply_reading_theme(self, theme):
        """Apply reading theme"""
        # Remove existing theme classes
        self.text_view.remove_css_class("sepia-theme")
        self.text_view.remove_css_class("night-theme")
        
        if theme == "sepia":
            self.text_view.add_css_class("sepia-theme")
            self.settings.set("reading_theme", "sepia")
        elif theme == "night":
            self.text_view.add_css_class("night-theme")
            self.settings.set("reading_theme", "night")
        else:
            self.settings.set("reading_theme", "default")
    
    def on_line_spacing_action(self, action, param):
        """Handle line spacing adjustment"""
        # Create line spacing dialog
        dialog = Adw.PreferencesDialog()
        dialog.set_title(_("Line Spacing"))
        
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        dialog.add(page)
        
        # Line spacing slider
        spacing_row = Adw.ActionRow()
        spacing_row.set_title(_("Line Spacing"))
        spacing_row.set_subtitle(_("Adjust spacing between lines"))
        
        spacing_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1.0, 2.5, 0.1)
        spacing_scale.set_value(self.settings.get("line_spacing", 1.5))
        spacing_scale.set_hexpand(True)
        spacing_row.add_suffix(spacing_scale)
        group.add(spacing_row)
        
        # Apply changes
        def on_spacing_changed(scale):
            value = scale.get_value()
            self.apply_line_spacing(value)
            self.settings.set("line_spacing", value)
        
        spacing_scale.connect('value-changed', on_spacing_changed)
        
        dialog.present(self.get_root())
    
    def apply_line_spacing(self, spacing):
        """Apply line spacing to text view"""
        # Update text tags
        if hasattr(self, 'normal_tag'):
            self.normal_tag.props.pixels_below_lines = int(spacing * 5)
    
    def on_dictionary_action(self, action, param):
        """Handle dictionary settings"""
        # For now, just show a placeholder
        toast = Adw.Toast(title=_("Dictionary settings - coming soon"))
        self.show_toast(toast)
    
    def on_statistics_action(self, action, param):
        """Show reading statistics"""
        if not self.current_book_path:
            return
        
        stats = self.user_data.get_reading_stats(self.current_book_path)
        
        # Create statistics dialog
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Reading Statistics"))
        
        # Format statistics
        total_time = stats.get('total_time', 0)
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        
        pages_read = stats.get('pages_read', 0)
        sessions = len(stats.get('sessions', []))
        
        stats_text = f"""
{_("Total reading time")}: {hours}h {minutes}m
{_("Pages read")}: {pages_read}
{_("Reading sessions")}: {sessions}
        """.strip()
        
        dialog.set_body(stats_text)
        dialog.add_response("close", _("Close"))
        dialog.present(self.get_root())
    
    def load_book(self, book_path):
        """Load book and restore reading position"""
        super().load_book(book_path)
        
        if self.current_book_path:
            # Start reading session
            self.reading_session_index = self.user_data.start_reading_session(self.current_book_path)
            
            # Restore reading position
            position = self.user_data.get_reading_position(self.current_book_path)
            if position and position.get('chapter_index', 0) < len(self.book_metadata.chapters):
                self.current_chapter = position['chapter_index']
                self.display_chapter(self.current_chapter)
                
                # Scroll to saved position
                if position.get('position', 0) > 0:
                    iter_pos = self.text_buffer.get_iter_at_offset(position['position'])
                    self.text_view.scroll_to_iter(iter_pos, 0.25, False, 0.0, 0.5)
            
            # Update sidebar lists
            self.update_bookmarks_list()
            self.update_annotations_list()
    
    def save_reading_position(self):
        """Save current reading position"""
        if self.current_book_path:
            # Get current position
            mark = self.text_buffer.get_insert()
            iter_pos = self.text_buffer.get_iter_at_mark(mark)
            position = iter_pos.get_offset()
            
            # Save position
            self.user_data.set_reading_position(self.current_book_path, self.current_chapter, position)
            
            # Update reading session
            if self.reading_session_index is not None:
                self.user_data.update_reading_session(
                    self.current_book_path, self.reading_session_index, 
                    pages_read=self.current_chapter + 1
                )
    
    def close_book(self):
        """Close book and save state"""
        if self.current_book_path:
            self.save_reading_position()
            
            # End reading session
            if self.reading_session_index is not None:
                self.user_data.end_reading_session(self.current_book_path, self.reading_session_index)
        
        self.current_book_path = None
        self.reading_session_index = None