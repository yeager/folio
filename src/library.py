"""
Library view for Folio
Shows grid of books with covers and metadata
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, GObject, GdkPixbuf, Gio, GLib
import os
import threading
import gettext

try:
    from .book_parser import create_parser
    from .utils import is_supported_format, get_file_type_description, get_book_cover_cache_path
except ImportError:
    # When running from source
    from book_parser import create_parser
    from utils import is_supported_format, get_file_type_description, get_book_cover_cache_path

_ = gettext.gettext


class BookItem(GObject.Object):
    """Data model for a book item"""
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.title = os.path.basename(file_path)
        self.author = ""
        self.description = ""
        self.cover_pixbuf = None
        self.file_size = 0
        self.last_modified = 0
        self.reading_position = 0
        
        # Get file info
        try:
            stat = os.stat(file_path)
            self.file_size = stat.st_size
            self.last_modified = stat.st_mtime
        except:
            pass


class LibraryView(Gtk.Box):
    """Library view widget"""
    
    __gsignals__ = {
        'book-selected': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'book-activated': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__(self, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.settings = settings
        self.books = []
        self.filtered_books = []
        
        self.setup_ui()
        self.scan_library()
    
    def setup_ui(self):
        """Set up the library UI"""
        # Header bar with controls
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(12)
        header.set_margin_end(12)
        header.set_margin_top(12)
        header.set_margin_bottom(6)
        
        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search books..."))
        self.search_entry.connect('search-changed', self.on_search_changed)
        header.append(self.search_entry)
        
        # View mode buttons
        view_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        view_box.add_css_class("linked")
        
        self.grid_button = Gtk.ToggleButton()
        self.grid_button.set_icon_name("view-grid-symbolic")
        self.grid_button.set_tooltip_text(_("Grid view"))
        self.grid_button.set_active(True)
        self.grid_button.connect('toggled', self.on_view_mode_changed)
        view_box.append(self.grid_button)
        
        self.list_button = Gtk.ToggleButton()
        self.list_button.set_icon_name("view-list-symbolic")
        self.list_button.set_tooltip_text(_("List view"))
        self.list_button.set_group(self.grid_button)
        view_box.append(self.list_button)
        
        header.append(view_box)
        
        # Add book button
        add_button = Gtk.Button()
        add_button.set_icon_name("list-add-symbolic")
        add_button.set_tooltip_text(_("Add books"))
        add_button.connect('clicked', self.on_add_books)
        header.append(add_button)
        
        # Refresh button
        refresh_button = Gtk.Button()
        refresh_button.set_icon_name("view-refresh-symbolic")
        refresh_button.set_tooltip_text(_("Refresh library"))
        refresh_button.connect('clicked', self.on_refresh)
        header.append(refresh_button)
        
        self.append(header)
        
        # Scrolled window for book view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        # Grid view
        self.grid_view = Gtk.GridView()
        self.grid_view.set_max_columns(6)
        self.grid_view.set_min_columns(2)
        
        # List store for books
        self.book_store = Gio.ListStore.new(BookItem)
        self.grid_view.set_model(Gtk.SingleSelection.new(self.book_store))
        
        # Item factory for grid view
        self.grid_factory = Gtk.SignalListItemFactory()
        self.grid_factory.connect('setup', self.on_grid_item_setup)
        self.grid_factory.connect('bind', self.on_grid_item_bind)
        self.grid_view.set_factory(self.grid_factory)
        
        # Connect selection
        selection = self.grid_view.get_model()
        selection.connect('selection-changed', self.on_selection_changed)
        
        # Connect activation (double-click)
        self.grid_view.connect('activate', self.on_item_activated)
        
        scrolled.set_child(self.grid_view)
        self.append(scrolled)
        
        # Status bar
        self.status_bar = Gtk.Label()
        self.status_bar.set_margin_start(12)
        self.status_bar.set_margin_end(12)
        self.status_bar.set_margin_bottom(6)
        self.status_bar.set_halign(Gtk.Align.START)
        self.status_bar.add_css_class("caption")
        self.append(self.status_bar)
        
        self.update_status()
    
    def on_grid_item_setup(self, factory, list_item):
        """Set up grid item widget"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_size_request(160, 240)
        
        # Cover image
        cover = Gtk.Image()
        cover.set_size_request(120, 160)
        cover.add_css_class("card")
        box.append(cover)
        
        # Book info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        title_label = Gtk.Label()
        title_label.set_ellipsize(3)  # ELLIPSIZE_END
        title_label.set_max_width_chars(20)
        title_label.set_lines(2)
        title_label.set_wrap(True)
        title_label.add_css_class("heading")
        info_box.append(title_label)
        
        author_label = Gtk.Label()
        author_label.set_ellipsize(3)
        author_label.set_max_width_chars(20)
        author_label.add_css_class("caption")
        info_box.append(author_label)
        
        box.append(info_box)
        
        list_item.set_child(box)
    
    def on_grid_item_bind(self, factory, list_item):
        """Bind data to grid item"""
        book = list_item.get_item()
        box = list_item.get_child()
        
        # Get widgets
        cover = box.get_first_child()
        info_box = box.get_last_child()
        title_label = info_box.get_first_child()
        author_label = info_box.get_last_child()
        
        # Set data
        title_label.set_text(book.title)
        author_label.set_text(book.author or _("Unknown author"))
        
        # Set cover
        if book.cover_pixbuf:
            cover.set_from_pixbuf(book.cover_pixbuf)
        else:
            cover.set_from_icon_name("text-x-generic-symbolic")
            # Load cover in background
            self.load_book_cover(book, cover)
    
    def load_book_cover(self, book, cover_widget):
        """Load book cover in background"""
        def cover_worker():
            try:
                # Check cache first
                cache_path = get_book_cover_cache_path(book.file_path)
                
                if os.path.exists(cache_path):
                    # Load from cache
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        cache_path, 120, 160, True
                    )
                    GLib.idle_add(self.set_cover_image, cover_widget, pixbuf)
                    return
                
                # Parse book to get cover
                parser = create_parser(book.file_path)
                metadata = parser.parse()
                
                if metadata.cover_data:
                    # Save to cache and display
                    with open(cache_path, 'wb') as f:
                        f.write(metadata.cover_data)
                    
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        cache_path, 120, 160, True
                    )
                    
                    book.cover_pixbuf = pixbuf
                    GLib.idle_add(self.set_cover_image, cover_widget, pixbuf)
            except Exception as e:
                print(f"Error loading cover for {book.file_path}: {e}")
        
        thread = threading.Thread(target=cover_worker)
        thread.daemon = True
        thread.start()
    
    def set_cover_image(self, cover_widget, pixbuf):
        """Set cover image on main thread"""
        cover_widget.set_from_pixbuf(pixbuf)
        return False  # Remove from idle queue
    
    def scan_library(self):
        """Scan library directory for books"""
        library_path = self.settings.get("library_path", "")
        if not library_path:
            docs = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)
            if not docs:
                docs = os.path.expanduser("~")
            library_path = os.path.join(docs, "Books")
        library_path = os.path.expanduser(library_path)
        
        if not os.path.exists(library_path):
            os.makedirs(library_path, exist_ok=True)
        
        def scan_worker():
            books = []
            try:
                for root, dirs, files in os.walk(library_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if is_supported_format(file_path):
                            book = BookItem(file_path)
                            
                            # Quick metadata extraction
                            try:
                                parser = create_parser(file_path)
                                metadata = parser.parse()
                                book.title = metadata.title or os.path.splitext(file)[0]
                                book.author = metadata.author
                                book.description = metadata.description
                            except:
                                book.title = os.path.splitext(file)[0]
                            
                            # Get reading position
                            book.reading_position = self.settings.get_reading_position(file_path)
                            
                            books.append(book)
            except Exception as e:
                print(f"Error scanning library: {e}")
            
            GLib.idle_add(self.update_book_list, books)
        
        thread = threading.Thread(target=scan_worker)
        thread.daemon = True
        thread.start()
    
    def update_book_list(self, books):
        """Update book list on main thread"""
        self.books = books
        self.apply_filter()
        return False
    
    def apply_filter(self):
        """Apply search filter to books"""
        search_text = self.search_entry.get_text().lower()
        
        if search_text:
            self.filtered_books = [
                book for book in self.books
                if (search_text in book.title.lower() or
                    search_text in book.author.lower())
            ]
        else:
            self.filtered_books = self.books[:]
        
        # Update store
        self.book_store.remove_all()
        for book in self.filtered_books:
            self.book_store.append(book)
        
        self.update_status()
    
    def update_status(self):
        """Update status bar"""
        total = len(self.books)
        filtered = len(self.filtered_books)
        
        if total != filtered:
            # Use proper singular/plural forms
            if filtered == 1:
                filtered_text = _("1 book")
            else:
                filtered_text = _("{} books").format(filtered)
            
            if total == 1:
                total_text = _("1 book")
            else:
                total_text = _("{} books").format(total)
            
            text = _("{} of {}").format(filtered_text, total_text)
        else:
            # Use ngettext for proper pluralization
            text = gettext.ngettext("{} book", "{} books", total).format(total)
        
        self.status_bar.set_text(text)
    
    def on_search_changed(self, entry):
        """Handle search text change"""
        self.apply_filter()
    
    def on_view_mode_changed(self, button):
        """Handle view mode change"""
        # For now, only grid view is implemented
        pass
    
    def on_selection_changed(self, selection, position, n_items):
        """Handle selection change"""
        selected = selection.get_selected_item()
        if selected:
            self.emit('book-selected', selected.file_path)
    
    def on_item_activated(self, grid_view, position):
        """Handle item activation (double-click)"""
        selection = grid_view.get_model()
        book = selection.get_item(position)
        if book:
            self.emit('book-activated', book.file_path)
    
    def on_add_books(self, button):
        """Handle add books button"""
        self.emit('book-selected', 'ADD_BOOKS')
    
    def on_refresh(self, button):
        """Handle refresh button"""
        self.scan_library()
    
    def refresh_library(self):
        """Refresh the library"""
        self.scan_library()