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
except ImportError:
    # When running from source
    from book_parser import create_parser
    from tts import TTSEngine

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
        
        # TTS engine
        self.tts_engine = TTSEngine()
        self.tts_engine.connect('word-started', self.on_word_started)
        self.tts_engine.connect('word-finished', self.on_word_finished)
        self.tts_engine.connect('speech-finished', self.on_speech_finished)
        self.tts_engine.connect('speech-error', self.on_speech_error)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the reader UI"""
        # Sidebar for table of contents
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar.set_size_request(250, -1)
        
        # TOC header
        toc_header = Gtk.Label(label=_("Table of Contents"))
        toc_header.add_css_class("heading")
        toc_header.set_margin_start(12)
        toc_header.set_margin_end(12)
        toc_header.set_margin_top(12)
        toc_header.set_margin_bottom(6)
        toc_header.set_halign(Gtk.Align.START)
        self.sidebar.append(toc_header)
        
        # TOC list
        scrolled_toc = Gtk.ScrolledWindow()
        scrolled_toc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.toc_list = Gtk.ListBox()
        self.toc_list.add_css_class("navigation-sidebar")
        self.toc_list.connect('row-selected', self.on_chapter_selected)
        scrolled_toc.set_child(self.toc_list)
        self.sidebar.append(scrolled_toc)
        
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
        
        self.play_button = Gtk.Button()
        self.play_button.set_icon_name("media-playback-start-symbolic")
        self.play_button.set_tooltip_text(_("Play/Pause"))
        self.play_button.connect('clicked', self.on_tts_play_pause)
        tts_box.append(self.play_button)
        
        self.stop_button = Gtk.Button()
        self.stop_button.set_icon_name("media-playback-stop-symbolic")
        self.stop_button.set_tooltip_text(_("Stop"))
        self.stop_button.connect('clicked', self.on_tts_stop)
        tts_box.append(self.stop_button)
        
        # Speed control (quick access)
        self.speed_button = Gtk.Button()
        self.speed_button.set_icon_name("multimedia-player-symbolic")
        self.speed_button.set_tooltip_text(_("Speech speed"))
        self.speed_button.connect('clicked', self.on_speed_clicked)
        tts_box.append(self.speed_button)
        
        toolbar.append(tts_box)
        
        # Settings button
        settings_button = Gtk.MenuButton()
        settings_button.set_icon_name("open-menu-symbolic")
        settings_button.set_tooltip_text(_("Reading settings"))
        
        # Settings menu
        settings_menu = Gio.Menu()
        settings_menu.append(_("Font size..."), "reader.font-size")
        settings_menu.append(_("TTS settings..."), "reader.tts-settings")
        settings_button.set_menu_model(settings_menu)
        
        toolbar.append(settings_button)
        
        main_box.append(toolbar)
        
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
        self.next_button.connect('clicked', self.on_next_chapter)
        nav_bar.append(self.next_button)
        
        main_box.append(nav_bar)
        
        self.append(main_box)
        
        # Create actions
        self.create_actions()
    
    def create_actions(self):
        """Create reader actions"""
        # Font size action
        font_action = Gio.SimpleAction.new("font-size", None)
        font_action.connect("activate", self.on_font_size_action)
        
        # TTS settings action
        tts_action = Gio.SimpleAction.new("tts-settings", None)
        tts_action.connect("activate", self.on_tts_settings_action)
        
        # Add actions to action group
        action_group = Gio.SimpleActionGroup()
        action_group.add_action(font_action)
        action_group.add_action(tts_action)
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