#!/usr/bin/env python3
"""
Setup script for Folio
"""

from setuptools import setup, find_packages
import os

# Read long description from README
long_description = """
Folio is a modern e-book reader built with GTK4 and libadwaita.
It supports all major e-book formats including EPUB, PDF, MOBI, and comic books.
The built-in text-to-speech feature uses Piper for high-quality offline speech synthesis.

Features:
- Clean, responsive interface with light/dark theme support
- Support for EPUB, PDF, MOBI, FB2, CBZ/CBR formats
- Text-to-speech with Swedish and English voices
- Auto page-turn during TTS playback
- Customizable font sizes and reading preferences
- Book library management with cover thumbnails
- Remember reading position for each book
- Full internationalization support
"""

setup(
    name='folio',
    version='1.0.0',
    description='Modern e-book reader with TTS support',
    long_description=long_description,
    long_description_content_type='text/plain',
    author='Daniel Nylander',
    author_email='daniel@danielnylander.se',
    url='https://github.com/yeager/folio',
    license='GPL-3.0+',
    
    packages=find_packages('src'),
    package_dir={'': 'src'},
    
    python_requires='>=3.8',
    
    install_requires=[
        'PyGObject>=3.42',
        'ebooklib>=0.18',
        'PyMuPDF>=1.20.0',
    ],
    
    extras_require={
        'dev': [
            'pytest',
            'black',
            'flake8',
            'mypy',
        ],
    },
    
    entry_points={
        'console_scripts': [
            'folio=folio.main:main',
        ],
    },
    
    data_files=[
        ('share/applications', ['data/se.danielnylander.folio.desktop']),
        ('share/metainfo', ['data/se.danielnylander.folio.metainfo.xml']),
        ('share/glib-2.0/schemas', ['data/se.danielnylander.folio.gschema.xml']),
    ],
    
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Multimedia :: Graphics :: Viewers',
        'Topic :: Text Processing',
    ],
    
    keywords='ebook epub pdf reader gtk tts piper',
    
    project_urls={
        'Bug Reports': 'https://github.com/yeager/folio/issues',
        'Source': 'https://github.com/yeager/folio',
    },
)