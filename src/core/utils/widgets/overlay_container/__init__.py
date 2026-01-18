from .overlay_background_media import OverlayBackgroundMedia

# Import OverlayBackgroundShader with error handling
# This allows the module to load even if OpenGL dependencies are missing
try:
    from .overlay_background_shader import OverlayBackgroundShader
except Exception as e:
    import logging
    logging.warning(f"Failed to import OverlayBackgroundShader: {e}")
    # Create a dummy class that does nothing
    class OverlayBackgroundShader:
        def __init__(self, *args, **kwargs):
            logging.warning("OverlayBackgroundShader unavailable - shader backgrounds will not work")
            self.widget = None
        def get_widget(self):
            return None
        def cleanup(self):
            pass

__all__ = ["OverlayBackgroundMedia", "OverlayBackgroundShader"]