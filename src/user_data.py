"""
User data management for Folio
Handles bookmarks, annotations, reading positions, and statistics
"""

import os
import json
import hashlib
import time
from gi.repository import GLib
import gettext

_ = gettext.gettext


class UserDataManager:
    """Manages user data storage"""
    
    def __init__(self):
        # Create user data directories
        self.data_dir = os.path.join(GLib.get_user_data_dir(), "folio")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.bookmarks_file = os.path.join(self.data_dir, "bookmarks.json")
        self.positions_file = os.path.join(self.data_dir, "positions.json")
        self.annotations_file = os.path.join(self.data_dir, "annotations.json")
        self.stats_file = os.path.join(self.data_dir, "stats.json")
        
        # Load data
        self.bookmarks_data = self._load_json(self.bookmarks_file, {})
        self.positions_data = self._load_json(self.positions_file, {})
        self.annotations_data = self._load_json(self.annotations_file, {})
        self.stats_data = self._load_json(self.stats_file, {})
    
    def _load_json(self, file_path, default):
        """Load JSON data from file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
        return default
    
    def _save_json(self, file_path, data):
        """Save data to JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving {file_path}: {e}")
    
    def _get_book_hash(self, book_path):
        """Get unique hash for book file"""
        try:
            # Use file path + size + mtime for hash
            stat = os.stat(book_path)
            hash_input = f"{book_path}{stat.st_size}{stat.st_mtime}"
            return hashlib.sha256(hash_input.encode()).hexdigest()
        except:
            return hashlib.sha256(book_path.encode()).hexdigest()
    
    # Bookmarks
    def get_bookmarks(self, book_path):
        """Get bookmarks for a book"""
        book_hash = self._get_book_hash(book_path)
        return self.bookmarks_data.get(book_hash, [])
    
    def add_bookmark(self, book_path, chapter_index, position, preview_text=""):
        """Add bookmark"""
        book_hash = self._get_book_hash(book_path)
        if book_hash not in self.bookmarks_data:
            self.bookmarks_data[book_hash] = []
        
        bookmark = {
            'chapter_index': chapter_index,
            'position': position,
            'preview_text': preview_text[:100],  # Limit preview length
            'timestamp': time.time()
        }
        
        # Check if bookmark already exists at this position
        for existing in self.bookmarks_data[book_hash]:
            if (existing['chapter_index'] == chapter_index and 
                abs(existing['position'] - position) < 50):  # Within 50 chars
                return False  # Bookmark already exists
        
        self.bookmarks_data[book_hash].append(bookmark)
        self.bookmarks_data[book_hash].sort(key=lambda x: (x['chapter_index'], x['position']))
        self._save_json(self.bookmarks_file, self.bookmarks_data)
        return True
    
    def remove_bookmark(self, book_path, chapter_index, position):
        """Remove bookmark"""
        book_hash = self._get_book_hash(book_path)
        if book_hash not in self.bookmarks_data:
            return False
        
        # Find and remove bookmark
        for i, bookmark in enumerate(self.bookmarks_data[book_hash]):
            if (bookmark['chapter_index'] == chapter_index and 
                abs(bookmark['position'] - position) < 50):
                del self.bookmarks_data[book_hash][i]
                self._save_json(self.bookmarks_file, self.bookmarks_data)
                return True
        return False
    
    # Reading positions
    def get_reading_position(self, book_path):
        """Get reading position for book"""
        book_hash = self._get_book_hash(book_path)
        return self.positions_data.get(book_hash, {'chapter_index': 0, 'position': 0})
    
    def set_reading_position(self, book_path, chapter_index, position):
        """Set reading position for book"""
        book_hash = self._get_book_hash(book_path)
        self.positions_data[book_hash] = {
            'chapter_index': chapter_index,
            'position': position,
            'timestamp': time.time()
        }
        self._save_json(self.positions_file, self.positions_data)
    
    # Annotations/Highlights
    def get_annotations(self, book_path):
        """Get annotations for book"""
        book_hash = self._get_book_hash(book_path)
        return self.annotations_data.get(book_hash, [])
    
    def add_annotation(self, book_path, chapter_index, start_pos, end_pos, 
                      text, annotation_type="highlight", color="yellow", comment=""):
        """Add text annotation/highlight"""
        book_hash = self._get_book_hash(book_path)
        if book_hash not in self.annotations_data:
            self.annotations_data[book_hash] = []
        
        annotation = {
            'chapter_index': chapter_index,
            'start_pos': start_pos,
            'end_pos': end_pos,
            'text': text[:500],  # Limit text length
            'type': annotation_type,
            'color': color,
            'comment': comment,
            'timestamp': time.time()
        }
        
        self.annotations_data[book_hash].append(annotation)
        self.annotations_data[book_hash].sort(key=lambda x: (x['chapter_index'], x['start_pos']))
        self._save_json(self.annotations_file, self.annotations_data)
    
    def remove_annotation(self, book_path, chapter_index, start_pos, end_pos):
        """Remove annotation"""
        book_hash = self._get_book_hash(book_path)
        if book_hash not in self.annotations_data:
            return False
        
        # Find and remove annotation
        for i, annotation in enumerate(self.annotations_data[book_hash]):
            if (annotation['chapter_index'] == chapter_index and 
                annotation['start_pos'] == start_pos and
                annotation['end_pos'] == end_pos):
                del self.annotations_data[book_hash][i]
                self._save_json(self.annotations_file, self.annotations_data)
                return True
        return False
    
    def export_annotations_markdown(self, book_path, book_title=""):
        """Export annotations as Markdown"""
        annotations = self.get_annotations(book_path)
        if not annotations:
            return ""
        
        md_content = f"# Highlights and Notes: {book_title}\n\n"
        md_content += f"Exported on {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        current_chapter = None
        for annotation in annotations:
            if annotation['chapter_index'] != current_chapter:
                current_chapter = annotation['chapter_index']
                md_content += f"## Chapter {current_chapter + 1}\n\n"
            
            # Color emoji mapping
            color_emoji = {
                'yellow': '🟡',
                'green': '🟢',
                'blue': '🔵',
                'red': '🔴',
                'orange': '🟠',
                'purple': '🟣'
            }
            
            emoji = color_emoji.get(annotation['color'], '📝')
            md_content += f"{emoji} **{annotation['type'].title()}**\n"
            md_content += f"> {annotation['text']}\n"
            
            if annotation.get('comment'):
                md_content += f"\n*Note: {annotation['comment']}*\n"
            
            md_content += "\n---\n\n"
        
        return md_content
    
    # Reading statistics
    def start_reading_session(self, book_path):
        """Start a new reading session"""
        book_hash = self._get_book_hash(book_path)
        if book_hash not in self.stats_data:
            self.stats_data[book_hash] = {
                'total_time': 0,
                'sessions': [],
                'pages_read': 0,
                'words_read': 0,
                'first_opened': time.time()
            }
        
        # Start new session
        session = {
            'start_time': time.time(),
            'end_time': None,
            'pages_read': 0,
            'time_spent': 0
        }
        
        self.stats_data[book_hash]['sessions'].append(session)
        return len(self.stats_data[book_hash]['sessions']) - 1  # Return session index
    
    def update_reading_session(self, book_path, session_index, pages_read=0):
        """Update current reading session"""
        book_hash = self._get_book_hash(book_path)
        if (book_hash in self.stats_data and 
            session_index < len(self.stats_data[book_hash]['sessions'])):
            
            session = self.stats_data[book_hash]['sessions'][session_index]
            session['pages_read'] = pages_read
            session['time_spent'] = time.time() - session['start_time']
            
            # Update totals
            total_pages = sum(s.get('pages_read', 0) for s in self.stats_data[book_hash]['sessions'])
            self.stats_data[book_hash]['pages_read'] = total_pages
    
    def end_reading_session(self, book_path, session_index):
        """End reading session"""
        book_hash = self._get_book_hash(book_path)
        if (book_hash in self.stats_data and 
            session_index < len(self.stats_data[book_hash]['sessions'])):
            
            session = self.stats_data[book_hash]['sessions'][session_index]
            session['end_time'] = time.time()
            session['time_spent'] = session['end_time'] - session['start_time']
            
            # Update total time
            total_time = sum(s.get('time_spent', 0) for s in self.stats_data[book_hash]['sessions'])
            self.stats_data[book_hash]['total_time'] = total_time
            
            self._save_json(self.stats_file, self.stats_data)
    
    def get_reading_stats(self, book_path):
        """Get reading statistics for book"""
        book_hash = self._get_book_hash(book_path)
        return self.stats_data.get(book_hash, {
            'total_time': 0,
            'sessions': [],
            'pages_read': 0,
            'words_read': 0,
            'first_opened': time.time()
        })
    
    def estimate_reading_time(self, book_path, total_words, current_position_ratio):
        """Estimate remaining reading time based on reading speed"""
        stats = self.get_reading_stats(book_path)
        
        if not stats.get('total_time') or not stats.get('words_read'):
            # Default reading speed: 250 WPM
            words_per_minute = 250
        else:
            # Calculate actual reading speed
            words_per_minute = stats['words_read'] / (stats['total_time'] / 60)
            words_per_minute = max(100, min(500, words_per_minute))  # Reasonable bounds
        
        # Calculate remaining words
        remaining_words = total_words * (1 - current_position_ratio)
        remaining_minutes = remaining_words / words_per_minute
        
        return remaining_minutes