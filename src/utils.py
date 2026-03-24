"""
Utility functions for Folio
"""

import os
import hashlib
from urllib.parse import urlparse
import gettext

_ = gettext.gettext


def get_book_cover_cache_path(book_path):
    """Get cache path for book cover"""
    from gi.repository import GLib
    
    cache_dir = os.path.join(GLib.get_user_cache_dir(), "folio", "covers")
    os.makedirs(cache_dir, exist_ok=True)
    
    # Create hash of book path for unique filename
    book_hash = hashlib.md5(book_path.encode()).hexdigest()
    return os.path.join(cache_dir, f"{book_hash}.png")


def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def get_supported_formats():
    """Get list of supported e-book formats"""
    return {
        ".epub": _("EPUB e-book"),
        ".pdf": _("PDF document"),
        ".mobi": _("Kindle MOBI"),
        ".azw": _("Kindle AZW"),
        ".azw3": _("Kindle AZW3"),
        ".fb2": _("FictionBook"),
        ".cbz": _("Comic book ZIP"),
        ".cbr": _("Comic book RAR"),
        ".txt": _("Plain text"),
        ".html": _("HTML document"),
        ".htm": _("HTML document")
    }


def is_supported_format(file_path):
    """Check if file format is supported"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in get_supported_formats()


def get_file_type_description(file_path):
    """Get human-readable file type description"""
    ext = os.path.splitext(file_path)[1].lower()
    formats = get_supported_formats()
    return formats.get(ext, _("Unknown format"))


def sanitize_filename(filename):
    """Sanitize filename for safe use"""
    # Remove or replace unsafe characters
    unsafe_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename


def wrap_text(text, width=80):
    """Simple text wrapping"""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 <= width:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines)


def escape_html(text):
    """Escape HTML special characters"""
    if not text:
        return ""
    
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text