"""
Settings management for Folio
"""

import gi

gi.require_version("Gio", "2.0")

from gi.repository import Gio, GLib
import json
import os


class Settings:
    """Application settings manager"""

    def __init__(self):
        # Try to use GSettings if schema is installed, otherwise fall back to JSON
        self.use_gsettings = False
        try:
            # Set schema dir if specified in environment
            if 'GSETTINGS_SCHEMA_DIR' in os.environ:
                schema_source = Gio.SettingsSchemaSource.new_from_directory(
                    os.environ['GSETTINGS_SCHEMA_DIR'],
                    Gio.SettingsSchemaSource.get_default(),
                    False
                )
                schema = schema_source.lookup("se.danielnylander.folio", False)
                if schema:
                    self.gsettings = Gio.Settings.new_full(schema, None, None)
                    self.use_gsettings = True
                else:
                    raise Exception("Schema not found")
            else:
                self.gsettings = Gio.Settings.new("se.danielnylander.folio")
                self.use_gsettings = True
        except Exception as e:
            print(f"Falling back to JSON settings: {e}")
            # Fall back to JSON file in user config directory
            self.config_dir = os.path.join(
                GLib.get_user_config_dir(), "folio"
            )
            os.makedirs(self.config_dir, exist_ok=True)
            self.settings_file = os.path.join(self.config_dir, "settings.json")
            self.load_settings()

    def load_settings(self):
        """Load settings from JSON file"""
        if self.use_gsettings:
            return
            
        self.settings = {
            "window-width": 1200,
            "window-height": 800,
            "window-maximized": False,
            "library-path": os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS), "Books"),
            "font-size": 14,
            "theme": "system",  # system, light, dark
            "tts-voice": "sv_SE-nst-medium",
            "tts-speed": 1.0,
            "auto-page-turn": True,
            "last-book": "",
            "reading-positions": {}  # book_path -> position
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to JSON file"""
        if self.use_gsettings:
            return
            
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        """Get a setting value"""
        if self.use_gsettings:
            try:
                # Map our keys to GSettings keys
                gsettings_key = key.replace("_", "-")
                if gsettings_key == "reading-positions":
                    # Special handling for complex data
                    return json.loads(self.gsettings.get_string(gsettings_key) or "{}")
                return self.gsettings.get_value(gsettings_key).unpack()
            except Exception as e:
                print(f"GSettings get error for {key}: {e}")
                return default
        else:
            return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value"""
        if self.use_gsettings:
            try:
                gsettings_key = key.replace("_", "-")
                if gsettings_key == "reading-positions":
                    # Special handling for complex data
                    self.gsettings.set_string(gsettings_key, json.dumps(value))
                else:
                    # Create appropriate GVariant based on value type
                    if isinstance(value, bool):
                        variant = GLib.Variant.new_boolean(value)
                    elif isinstance(value, int):
                        variant = GLib.Variant.new_int32(value)
                    elif isinstance(value, float):
                        variant = GLib.Variant.new_double(value)
                    elif isinstance(value, str):
                        variant = GLib.Variant.new_string(value)
                    else:
                        variant = GLib.Variant.new_string(str(value))
                    self.gsettings.set_value(gsettings_key, variant)
            except Exception as e:
                print(f"GSettings error for {key}: {e}, falling back to JSON")
                # If GSettings fails, fall back to JSON
                self._fallback_to_json(key, value)
        else:
            self.settings[key] = value
            self.save_settings()
    
    def _fallback_to_json(self, key, value):
        """Fallback to JSON storage when GSettings fails"""
        if not hasattr(self, 'settings'):
            self.load_settings()
        self.settings[key] = value
        self.save_settings()

    def get_reading_position(self, book_path):
        """Get reading position for a book"""
        positions = self.get("reading_positions", {})
        return positions.get(book_path, 0)

    def set_reading_position(self, book_path, position):
        """Set reading position for a book"""
        positions = self.get("reading_positions", {})
        positions[book_path] = position
        self.set("reading_positions", positions)