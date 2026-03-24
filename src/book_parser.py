"""
Book format parsers for Folio
"""

import os
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
import gettext
import json
import tempfile
import subprocess
import re

_ = gettext.gettext


class BookMetadata:
    """Container for book metadata"""
    
    def __init__(self):
        self.title = ""
        self.author = ""
        self.description = ""
        self.language = ""
        self.publisher = ""
        self.pub_date = ""
        self.identifier = ""
        self.cover_data = None
        self.cover_mime_type = None
        self.chapters = []  # List of (title, content) tuples
        self.toc = []  # Table of contents


class BaseBookParser:
    """Base class for book parsers"""
    
    def __init__(self, file_path):
        self.file_path = file_path
    
    def parse(self):
        """Parse the book and return BookMetadata"""
        raise NotImplementedError
    
    def get_chapter_content(self, chapter_index):
        """Get content for a specific chapter"""
        raise NotImplementedError


class EPUBParser(BaseBookParser):
    """EPUB format parser"""
    
    def parse(self):
        metadata = BookMetadata()
        
        try:
            # Try with ebooklib first
            try:
                import ebooklib
                from ebooklib import epub
                
                book = epub.read_epub(self.file_path)
                
                # Extract metadata
                metadata.title = book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else os.path.basename(self.file_path)
                metadata.author = ', '.join([author[0] for author in book.get_metadata('DC', 'creator')])
                metadata.description = book.get_metadata('DC', 'description')[0][0] if book.get_metadata('DC', 'description') else ""
                metadata.language = book.get_metadata('DC', 'language')[0][0] if book.get_metadata('DC', 'language') else ""
                metadata.publisher = book.get_metadata('DC', 'publisher')[0][0] if book.get_metadata('DC', 'publisher') else ""
                
                # Extract chapters
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        content = item.get_content().decode('utf-8')
                        # Simple HTML to text conversion
                        text_content = self._html_to_text(content)
                        if text_content.strip():
                            metadata.chapters.append((item.get_name(), text_content))
                
                # Try to get cover
                cover_item = None
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_COVER or 'cover' in item.get_name().lower():
                        cover_item = item
                        break
                
                if cover_item:
                    metadata.cover_data = cover_item.get_content()
                    metadata.cover_mime_type = cover_item.media_type
                
            except ImportError:
                # Fall back to manual ZIP parsing
                metadata = self._parse_epub_manual()
                
        except Exception as e:
            print(f"Error parsing EPUB: {e}")
            metadata.title = os.path.basename(self.file_path)
        
        return metadata
    
    def _parse_epub_manual(self):
        """Manual EPUB parsing without ebooklib"""
        metadata = BookMetadata()
        
        try:
            with zipfile.ZipFile(self.file_path, 'r') as epub_zip:
                # Find OPF file
                opf_path = None
                try:
                    container_xml = epub_zip.read('META-INF/container.xml')
                    container_root = ET.fromstring(container_xml)
                    rootfile = container_root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
                    if rootfile is not None:
                        opf_path = rootfile.get('full-path')
                except:
                    # Look for .opf files
                    for name in epub_zip.namelist():
                        if name.endswith('.opf'):
                            opf_path = name
                            break
                
                if opf_path:
                    opf_content = epub_zip.read(opf_path)
                    opf_root = ET.fromstring(opf_content)
                    
                    # Extract metadata
                    ns = {'dc': 'http://purl.org/dc/elements/1.1/', 'opf': 'http://www.idpf.org/2007/opf'}
                    
                    title_elem = opf_root.find('.//dc:title', ns)
                    metadata.title = title_elem.text if title_elem is not None else os.path.basename(self.file_path)
                    
                    author_elem = opf_root.find('.//dc:creator', ns)
                    metadata.author = author_elem.text if author_elem is not None else ""
                    
                    desc_elem = opf_root.find('.//dc:description', ns)
                    metadata.description = desc_elem.text if desc_elem is not None else ""
                    
                    # Extract cover image
                    cover_data, cover_mime = self._extract_epub_cover(epub_zip, opf_root, opf_path, ns)
                    if cover_data:
                        metadata.cover_data = cover_data
                        metadata.cover_mime_type = cover_mime
                    
                    # Get content files
                    manifest = opf_root.find('.//opf:manifest', ns)
                    spine = opf_root.find('.//opf:spine', ns)
                    
                    if manifest is not None and spine is not None:
                        # Build file map
                        file_map = {}
                        for item in manifest.findall('.//opf:item', ns):
                            file_map[item.get('id')] = item.get('href')
                        
                        # Read chapters in order
                        opf_dir = os.path.dirname(opf_path)
                        for itemref in spine.findall('.//opf:itemref', ns):
                            idref = itemref.get('idref')
                            if idref in file_map:
                                chapter_path = os.path.join(opf_dir, file_map[idref]).replace('\\', '/')
                                try:
                                    chapter_content = epub_zip.read(chapter_path).decode('utf-8')
                                    text_content = self._html_to_text(chapter_content)
                                    if text_content.strip():
                                        metadata.chapters.append((file_map[idref], text_content))
                                except:
                                    pass
        
        except Exception as e:
            print(f"Error in manual EPUB parsing: {e}")
            metadata.title = os.path.basename(self.file_path)
        
        return metadata
    
    def _extract_epub_cover(self, epub_zip, opf_root, opf_path, ns):
        """Extract cover image from EPUB"""
        try:
            opf_dir = os.path.dirname(opf_path)
            
            # Method 1: Look for cover-image in metadata
            meta_cover = opf_root.find('.//opf:meta[@name="cover"]', ns)
            if meta_cover is not None:
                cover_id = meta_cover.get('content')
                if cover_id:
                    # Find the cover item in manifest
                    cover_item = opf_root.find(f'.//opf:item[@id="{cover_id}"]', ns)
                    if cover_item is not None:
                        cover_href = cover_item.get('href')
                        cover_type = cover_item.get('media-type', 'image/jpeg')
                        if cover_href:
                            cover_path = os.path.join(opf_dir, cover_href).replace('\\', '/')
                            try:
                                cover_data = epub_zip.read(cover_path)
                                return cover_data, cover_type
                            except:
                                pass
            
            # Method 2: Look for manifest items with properties="cover-image"
            cover_items = opf_root.findall('.//opf:item[@properties="cover-image"]', ns)
            for cover_item in cover_items:
                cover_href = cover_item.get('href')
                cover_type = cover_item.get('media-type', 'image/jpeg')
                if cover_href:
                    cover_path = os.path.join(opf_dir, cover_href).replace('\\', '/')
                    try:
                        cover_data = epub_zip.read(cover_path)
                        return cover_data, cover_type
                    except:
                        pass
            
            # Method 3: Look for common cover file names
            cover_patterns = ['cover', 'Cover', 'COVER', 'cover-image', 'coverpage']
            for pattern in cover_patterns:
                for ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    possible_names = [
                        f"{pattern}{ext}",
                        f"images/{pattern}{ext}",
                        f"Images/{pattern}{ext}",
                        f"OEBPS/images/{pattern}{ext}",
                        f"OEBPS/Images/{pattern}{ext}"
                    ]
                    
                    for name in possible_names:
                        try:
                            cover_data = epub_zip.read(name)
                            # Determine MIME type from extension
                            mime_type = {
                                '.jpg': 'image/jpeg',
                                '.jpeg': 'image/jpeg', 
                                '.png': 'image/png',
                                '.gif': 'image/gif'
                            }.get(ext.lower(), 'image/jpeg')
                            return cover_data, mime_type
                        except:
                            continue
            
            # Method 4: Find first image in spine
            manifest = opf_root.find('.//opf:manifest', ns)
            spine = opf_root.find('.//opf:spine', ns)
            
            if manifest is not None and spine is not None:
                # Build file map
                file_map = {}
                for item in manifest.findall('.//opf:item', ns):
                    file_map[item.get('id')] = {
                        'href': item.get('href'),
                        'media_type': item.get('media-type', '')
                    }
                
                # Check first few spine items for images
                for i, itemref in enumerate(spine.findall('.//opf:itemref', ns)[:3]):  # Check first 3 items
                    idref = itemref.get('idref')
                    if idref in file_map:
                        chapter_path = os.path.join(opf_dir, file_map[idref]['href']).replace('\\', '/')
                        try:
                            chapter_content = epub_zip.read(chapter_path).decode('utf-8')
                            # Look for img tags
                            import re
                            img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', chapter_content, re.IGNORECASE)
                            
                            for img_src in img_matches:
                                # Resolve relative path
                                img_path = os.path.join(os.path.dirname(chapter_path), img_src).replace('\\', '/')
                                try:
                                    img_data = epub_zip.read(img_path)
                                    # Determine MIME type
                                    ext = os.path.splitext(img_src)[1].lower()
                                    mime_type = {
                                        '.jpg': 'image/jpeg',
                                        '.jpeg': 'image/jpeg', 
                                        '.png': 'image/png',
                                        '.gif': 'image/gif'
                                    }.get(ext, 'image/jpeg')
                                    return img_data, mime_type
                                except:
                                    continue
                        except:
                            pass
            
        except Exception as e:
            print(f"Error extracting EPUB cover: {e}")
        
        return None, None
    
    def _html_to_text(self, html_content):
        """Convert HTML to plain text"""
        # Simple HTML tag removal
        import re
        
        # Remove script and style tags completely
        html_content = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert common tags to text equivalents
        html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<p\s*[^>]*>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</p>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<h[1-6][^>]*>', '\n\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</h[1-6]>', '\n', html_content, flags=re.IGNORECASE)
        
        # Remove all other HTML tags
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        html_content = html_content.replace('&lt;', '<')
        html_content = html_content.replace('&gt;', '>')
        html_content = html_content.replace('&amp;', '&')
        html_content = html_content.replace('&quot;', '"')
        html_content = html_content.replace('&#39;', "'")
        html_content = html_content.replace('&nbsp;', ' ')
        
        # Clean up whitespace
        html_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', html_content)
        html_content = re.sub(r'[ \t]+', ' ', html_content)
        
        return html_content.strip()


class PDFParser(BaseBookParser):
    """PDF format parser"""
    
    def parse(self):
        metadata = BookMetadata()
        
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(self.file_path)
            
            # Extract metadata
            doc_metadata = doc.metadata
            metadata.title = doc_metadata.get('title', os.path.basename(self.file_path))
            metadata.author = doc_metadata.get('author', '')
            metadata.description = doc_metadata.get('subject', '')
            
            # Extract text from all pages
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                full_text += page.get_text() + "\n\n"
            
            # Split into chapters (simple approach - split by page for now)
            pages_per_chapter = max(1, len(doc) // 20)  # Roughly 20 chapters max
            for i in range(0, len(doc), pages_per_chapter):
                chapter_text = ""
                for page_num in range(i, min(i + pages_per_chapter, len(doc))):
                    page = doc[page_num]
                    chapter_text += page.get_text() + "\n\n"
                
                if chapter_text.strip():
                    chapter_title = f"{_('Chapter')} {len(metadata.chapters) + 1}"
                    metadata.chapters.append((chapter_title, chapter_text))
            
            doc.close()
            
        except ImportError:
            print("PyMuPDF not available, PDF support limited")
            metadata.title = os.path.basename(self.file_path)
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            metadata.title = os.path.basename(self.file_path)
        
        return metadata


class TextParser(BaseBookParser):
    """Plain text parser"""
    
    def parse(self):
        metadata = BookMetadata()
        metadata.title = os.path.splitext(os.path.basename(self.file_path))[0]
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple chapter detection - split on double newlines or chapter markers
            chapters = []
            current_chapter = ""
            lines = content.split('\n')
            
            chapter_num = 1
            for line in lines:
                # Check for chapter markers
                if (re.match(r'^\s*chapter\s+\d+', line, re.IGNORECASE) or
                    re.match(r'^\s*\d+\.\s+', line) or
                    (len(line.strip()) < 50 and line.strip().isupper() and current_chapter)):
                    
                    if current_chapter.strip():
                        chapters.append((f"{_('Chapter')} {chapter_num}", current_chapter))
                        chapter_num += 1
                    current_chapter = line + '\n'
                else:
                    current_chapter += line + '\n'
            
            # Add final chapter
            if current_chapter.strip():
                chapters.append((f"{_('Chapter')} {chapter_num}", current_chapter))
            
            # If no chapters found, treat whole text as one chapter
            if not chapters:
                chapters.append((metadata.title, content))
            
            metadata.chapters = chapters
            
        except Exception as e:
            print(f"Error parsing text file: {e}")
            metadata.chapters = [(metadata.title, f"Error reading file: {e}")]
        
        return metadata


class ComicParser(BaseBookParser):
    """Comic book (CBZ/CBR) parser"""
    
    def parse(self):
        metadata = BookMetadata()
        metadata.title = os.path.splitext(os.path.basename(self.file_path))[0]
        
        try:
            if self.file_path.lower().endswith('.cbz'):
                with zipfile.ZipFile(self.file_path, 'r') as comic_zip:
                    image_files = sorted([f for f in comic_zip.namelist() 
                                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
                    
                    # Each image is a "page"
                    for i, image_file in enumerate(image_files):
                        try:
                            image_data = comic_zip.read(image_file)
                            # Store image as "text" content (we'll handle display differently)
                            metadata.chapters.append((f"{_('Page')} {i+1}", f"IMAGE:{image_file}:{len(image_data)}"))
                        except:
                            pass
            
            elif self.file_path.lower().endswith('.cbr'):
                # CBR requires rarfile library or external unrar
                metadata.chapters = [(metadata.title, _("CBR format requires additional software to read"))]
        
        except Exception as e:
            print(f"Error parsing comic: {e}")
            metadata.chapters = [(metadata.title, f"Error reading comic: {e}")]
        
        return metadata


def create_parser(file_path):
    """Create appropriate parser for the file"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.epub':
        return EPUBParser(file_path)
    elif ext == '.pdf':
        return PDFParser(file_path)
    elif ext in ['.txt', '.html', '.htm']:
        return TextParser(file_path)
    elif ext in ['.cbz', '.cbr']:
        return ComicParser(file_path)
    elif ext in ['.mobi', '.azw', '.azw3']:
        # For now, treat MOBI files as plain text after conversion
        return TextParser(file_path)
    elif ext == '.fb2':
        # FictionBook is XML-based
        return TextParser(file_path)
    else:
        # Default to text parser
        return TextParser(file_path)