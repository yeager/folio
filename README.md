# Folio - The Book Reader

A modern e-book reader built with GTK4 and libadwaita, featuring integrated text-to-speech support with Piper TTS.

![Folio Screenshot](screenshots/library.png)

## Features

- **Modern GTK4 Interface**: Clean, responsive design with libadwaita styling
- **Multi-format Support**: EPUB, PDF, MOBI, FB2, CBZ/CBR comic books
- **Text-to-Speech**: Integrated Piper TTS with Swedish and English voices
- **Smart Reading**: Auto page-turn, reading position memory, customizable fonts
- **Library Management**: Grid view with cover thumbnails, search functionality
- **Internationalization**: Full i18n support with Swedish translation
- **Accessibility**: High contrast themes, keyboard navigation

## Requirements

- Python 3.8+
- GTK4 (>= 4.8)
- libadwaita (>= 1.2)
- PyGObject
- Piper TTS (for text-to-speech functionality)

### Python Dependencies

```bash
pip install PyGObject ebooklib PyMuPDF
```

### System Dependencies (Ubuntu/Debian)

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
                 meson ninja-build gettext appstream-util desktop-file-utils
```

### System Dependencies (Fedora)

```bash
sudo dnf install python3-gobject gtk4-devel libadwaita-devel \
                 meson ninja-build gettext appstream desktop-file-utils
```

## Installation

### From Source

1. Clone the repository:
```bash
git clone https://github.com/yeager/folio.git
cd folio
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Build and install with Meson:
```bash
meson setup builddir
ninja -C builddir
sudo ninja -C builddir install
```

### Using pip

```bash
pip install folio
```

### Flatpak

```bash
flatpak install flathub se.danielnylander.folio
```

## Setting up Piper TTS

Folio uses Piper TTS for high-quality offline text-to-speech. To enable TTS functionality:

1. **Install Piper**:
   - Download from [Piper releases](https://github.com/rhasspy/piper/releases)
   - Or install via package manager (if available)
   - Or use pip: `pip install piper-tts`

2. **Install Voice Models**:
   - Swedish: Download `sv_SE-nst-medium` from Piper models
   - English: Download `en_US-lessac-medium` from Piper models
   - Place models in `/usr/share/piper/voices/` or `~/.local/share/piper/voices/`

3. **Verify Installation**:
   ```bash
   piper --help
   echo "Hello world" | piper --model en_US-lessac-medium --output-raw | aplay -r 22050 -f S16_LE -t raw
   ```

## Usage

### Starting the Application

```bash
folio
```

Or from the desktop applications menu.

### Adding Books

1. Click the "Add books" button in the library view
2. Select e-book files from the file dialog
3. Books will be automatically added to your library

### Reading

- Double-click a book to open it
- Use the table of contents for navigation
- Adjust font size and theme in preferences
- Use TTS controls to listen to books

### Text-to-Speech

1. Open a book
2. Click the play button in the toolbar
3. Configure voice and speed in TTS settings
4. Enable auto page-turn for continuous listening

## Development

### Running from Source

```bash
cd src
python3 -m folio.main
```

### Building Translations

```bash
ninja -C builddir folio-pot
ninja -C builddir folio-update-po
```

### Running Tests

```bash
python3 -m pytest tests/
```

### Code Formatting

```bash
black src/
flake8 src/
```

## Configuration

Folio stores its configuration using GSettings. You can view and modify settings using:

```bash
gsettings list-recursively se.danielnylander.folio
```

### Key Settings

- `library-path`: Path to your book collection
- `font-size`: Reading font size
- `tts-voice`: Piper voice model to use
- `tts-speed`: Speech rate (0.5 - 2.0)
- `theme`: Color theme (system/light/dark)

## File Format Support

| Format | Support | Notes |
|--------|---------|-------|
| EPUB   | ✅ Full | Native support via ebooklib |
| PDF    | ✅ Full | Text extraction via PyMuPDF |
| MOBI   | ⚠️ Basic | Text extraction only |
| AZW/AZW3 | ⚠️ Basic | Limited support |
| FB2    | ✅ Full | XML-based format |
| CBZ    | ✅ Full | Comic book ZIP archives |
| CBR    | ⚠️ Limited | Requires unrar |
| TXT    | ✅ Full | Plain text files |
| HTML   | ✅ Full | HTML documents |

## Keyboard Shortcuts

- `Ctrl+O`: Open book
- `Ctrl+Q`: Quit application
- `F11`: Toggle fullscreen
- `Left/Right Arrow`: Previous/next chapter
- `Space`: Play/pause TTS
- `Escape`: Stop TTS

## Troubleshooting

### TTS Not Working

1. Verify Piper installation: `piper --help`
2. Check voice models are installed
3. Test audio output: `speaker-test`
4. Check TTS settings in preferences

### Books Not Loading

1. Verify file format is supported
2. Check file permissions
3. Try opening file manually with parser
4. Check application logs

### Performance Issues

1. Reduce library scan depth
2. Clear cover cache: `~/.cache/folio/covers/`
3. Use smaller voice models
4. Disable auto page-turn

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

### Translation

To add a new language:

1. Add language code to `po/LINGUAS`
2. Create `po/LANG.po` from `po/folio.pot`
3. Translate strings
4. Test with `LANGUAGE=LANG folio`

## License

GPL-3.0+ - See LICENSE file for details.

## Credits

- **Author**: Daniel Nylander
- **Text-to-Speech**: [Piper](https://github.com/rhasspy/piper) by Rhasspy
- **UI Framework**: GTK4 and libadwaita
- **Icons**: GNOME icon theme

## Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/yeager/folio/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yeager/folio/discussions)
- 📧 **Email**: daniel@danielnylander.se

---

*Folio - Because every book deserves to be heard.*