from gi.repository import Gtk

class SmoothScrolledWindow(Gtk.ScrolledWindow):
    """
    A simple wrapper for Gtk.ScrolledWindow to maintain compatibility.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)