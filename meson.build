project('folio',
        version: '1.0.0',
        meson_version: '>= 0.59.0',
        default_options: ['warning_level=2',
                         'werror=false'])

# Project information
app_id = 'se.danielnylander.folio'
python = import('python')

# Dependencies
dependency('glib-2.0')
dependency('gtk4', version: '>= 4.8')
dependency('libadwaita-1', version: '>= 1.2')

# Python installation
py_installation = python.find_installation('python3')
if not py_installation.found()
    error('Python 3 is required but not found')
endif

# Check for required Python modules
required_modules = ['gi', 'ebooklib', 'PyMuPDF']
foreach module : required_modules
    if not py_installation.language_version().version_compare('>=3.8')
        error('Python >= 3.8 is required')
    endif
endforeach

# Directories
prefix = get_option('prefix')
bindir = prefix / get_option('bindir')
datadir = prefix / get_option('datadir')
pkgdatadir = datadir / meson.project_name()
pythondir = py_installation.get_install_dir()

# Configuration
conf = configuration_data()
conf.set('PYTHON', py_installation.full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', prefix / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

# Subdirectories
subdir('data')
subdir('src')
subdir('po')

# Post install script
gnome = import('gnome')

# Install schemas
install_data(
  'data' / 'se.danielnylander.folio.gschema.xml',
  install_dir: datadir / 'glib-2.0' / 'schemas'
)

# Post install actions
meson.add_install_script('build-aux/meson/postinstall.py')

# Summary
summary({'prefix': get_option('prefix'),
         'bindir': bindir,
         'datadir': datadir,
        }, section: 'Directories')
summary({'Profile': get_option('profile'),
        }, section: 'Build')

# Create postinstall script
postinstall_script = '''#!/usr/bin/env python3

import os
import subprocess
import sys

if not os.environ.get('DESTDIR'):
    print('Compiling GSettings schemas...')
    subprocess.call(['glib-compile-schemas', sys.argv[1]])
    
    print('Updating desktop database...')
    subprocess.call(['update-desktop-database', '-q', sys.argv[2]])
    
    print('Updating icon cache...')
    subprocess.call(['gtk-update-icon-cache', '-q', '-t', '-f', sys.argv[3]])
'''

# Create build-aux directory and postinstall script
build_aux_dir = meson.current_source_dir() / 'build-aux' / 'meson'
import('fs').mkdir(build_aux_dir)

postinstall_py = configure_file(
    input: files(),
    output: 'postinstall.py',
    configuration: {'postinstall_script': postinstall_script},
    install: false
)

# Create actual postinstall script
run_command('mkdir', '-p', build_aux_dir, check: true)
run_command('python3', '-c', 
    '''
import os
with open("''' + build_aux_dir + '''/postinstall.py", "w") as f:
    f.write("""#!/usr/bin/env python3

import os
import subprocess
import sys

if not os.environ.get('DESTDIR'):
    print('Compiling GSettings schemas...')
    subprocess.call(['glib-compile-schemas', sys.argv[1]])
    
    print('Updating desktop database...')
    subprocess.call(['update-desktop-database', '-q', sys.argv[2]])
    
    print('Updating icon cache...')
    subprocess.call(['gtk-update-icon-cache', '-q', '-t', '-f', sys.argv[3]])
""")
os.chmod("''' + build_aux_dir + '''/postinstall.py", 0o755)
''', check: false)