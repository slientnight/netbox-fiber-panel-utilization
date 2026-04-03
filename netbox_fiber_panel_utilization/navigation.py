"""Navigation menu items for the fiber patch panel utilization plugin.

This module provides the ``menu_items`` tuple that NetBox discovers
automatically.  Because the plugin's detail page requires a ``device_id``
URL parameter, there is no natural list/landing page to link from the
navigation menu.  The primary entry point for users is the utilization
widget injected into each supported device's detail page.

The ``menu_items`` tuple is left empty so that the plugin integrates
cleanly via the NetBox plugin navigation API (Req 9.3) without
registering a broken menu link.  If a landing page is added in the
future, a ``PluginMenuItem`` can be appended here.
"""

try:
    from netbox.plugins import PluginMenuItem  # noqa: F401
except ImportError:
    pass

# No list/landing page exists; the widget on the device page is the
# primary entry point.  Kept as an empty tuple so NetBox's plugin
# loader finds a valid ``menu_items`` attribute.
menu_items = ()
