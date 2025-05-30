# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

# Importar el diálogo
from .plugin_dialog import PluginDialog

class MainPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu_name = "&Análisis Redes Transporte" # Nombre del menú
        self.toolbar = self.iface.addToolBar("AnálisisRedesPluginToolbar")
        self.toolbar.setObjectName("AnálisisRedesPluginToolbar")
        self.dialog = None # Para mantener una única instancia del diálogo

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        
        self.action = QAction(QIcon(icon_path), 
                              "Herramientas de Análisis de Redes", 
                              self.iface.mainWindow())
        self.action.setObjectName("analisisRedesTransporteAction")
        self.action.setWhatsThis("Abrir el plugin de Análisis de Redes de Transporte")
        self.action.setStatusTip("Abrir el plugin de Análisis de Redes de Transporte")
        
        self.action.triggered.connect(self.run)

        self.toolbar.addAction(self.action)
        self.iface.addPluginToMenu(self.menu_name, self.action)
        
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu_name, action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar
        
        # Limpiar la instancia del diálogo si existe
        if self.dialog:
            del self.dialog
            self.dialog = None

    def run(self):
        # Crear y mostrar el diálogo.
        # Si ya existe una instancia, simplemente muéstrala.
        # Esto evita múltiples ventanas del mismo plugin.
        if self.dialog is None:
            self.dialog = PluginDialog(self.iface, self.iface.mainWindow())
        
        # Limpiar campos antes de mostrar, si es necesario (opcional)
        # self.dialog.limpiar_campos_dro() 
        # self.dialog.limpiar_campos_dai()
        # self.dialog.limpiar_campos_dumc()
        
        self.dialog.show()
        # El resultado de exec_() puede ser usado si el diálogo es modal
        # result = self.dialog.exec_()
        # if result:
        #     pass # Manejar aceptación si es necesario