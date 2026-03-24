# Source files

moduledir = pythondir / 'folio'

python_sources = [
  '__init__.py',
  'application.py',
  'book_parser.py',
  'library.py',
  'main.py',
  'reader.py',
  'settings.py',
  'tts.py',
  'utils.py',
  'window.py',
]

install_data(python_sources, install_dir: moduledir)

# Create launcher script
launcher = configure_file(
  input: 'launcher.py.in',
  output: 'folio',
  configuration: conf,
  install: true,
  install_dir: bindir,
  install_mode: 'rwxr-xr-x'
)