# -*- coding: utf-8 -*-

def classFactory(iface):
    """Carga la clase MainPlugin desde el módulo main_plugin.

    :param iface: Una instancia de QgisInterface.
    :type iface: QgsInterface
    :returns: Instancia de la clase principal del plugin.
    :rtype: MainPlugin
    """
    from .main_plugin import MainPlugin
    return MainPlugin(iface)