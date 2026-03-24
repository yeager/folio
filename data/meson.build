# Data files

# Desktop file
desktop_file = i18n.merge_file(
  input: 'se.danielnylander.folio.desktop',
  output: 'se.danielnylander.folio.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: datadir / 'applications'
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils,
    args: [desktop_file]
  )
endif

# AppStream metainfo
appstream_file = i18n.merge_file(
  input: 'se.danielnylander.folio.metainfo.xml',
  output: 'se.danielnylander.folio.metainfo.xml',
  po_dir: '../po',
  install: true,
  install_dir: datadir / 'metainfo'
)

appstream_util = find_program('appstream-util', required: false)
if appstream_util.found()
  test('Validate appstream file', appstream_util,
    args: ['validate', appstream_file]
  )
endif

# GSettings schema (installed in main meson.build)

# Install icons (if any)
# icons_dir = 'icons'
# install_subdir(icons_dir, install_dir: datadir / 'icons' / 'hicolor')