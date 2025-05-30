# -*- coding: utf-8 -*-
import os
import traceback
import webbrowser  # <--- MODIFICACIÓN: Añadido para abrir el navegador

from qgis.PyQt import uic
# <--- MODIFICACIÓN: Añadido QDialogButtonBox
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QDialogButtonBox
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    Qgis,
    QgsMapLayerProxyModel,
    QgsMessageLog,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem
)
from qgis.gui import QgsFileWidget

from . import network_algorithms

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'plugin_dialog_base.ui'))


class PluginDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super(PluginDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface

        self.mMapLayerComboBox_dro_vias.setFilters(
            QgsMapLayerProxyModel.LineLayer)
        self.mMapLayerComboBox_dro_puntos.setFilters(
            QgsMapLayerProxyModel.PointLayer)
        self.mMapLayerComboBox_dai_vias.setFilters(
            QgsMapLayerProxyModel.LineLayer)
        self.mMapLayerComboBox_dai_puntos.setFilters(
            QgsMapLayerProxyModel.PointLayer)
        self.mMapLayerComboBox_dumc_vias.setFilters(
            QgsMapLayerProxyModel.LineLayer)
        self.mMapLayerComboBox_dumc_puntos1.setFilters(
            QgsMapLayerProxyModel.PointLayer)
        self.mMapLayerComboBox_dumc_puntos2.setFilters(
            QgsMapLayerProxyModel.PointLayer)

        self._conectar_field_comboboxes()
        self._configurar_file_widgets()
        self._conectar_botones_examinar()

        self.pushButton_run_dro.clicked.connect(self.run_dro)
        self.pushButton_run_dai.clicked.connect(self.run_dai)
        self.pushButton_run_dumc.clicked.connect(self.run_dumc)

        self.tabWidgetMain.currentChanged.connect(
            self.actualizar_descripcion_tab)
        self.actualizar_descripcion_tab(self.tabWidgetMain.currentIndex())

        # El botón de cerrar (reject) es manejado por la conexión del .ui, pero lo dejamos explícito
        self.buttonBox_main.rejected.connect(self.reject)

        # --- INICIO DE LA MODIFICACIÓN ---
        # Añadir un botón de Ayuda programáticamente al QDialogButtonBox
        self.help_button = self.buttonBox_main.addButton(
            "Ayuda", QDialogButtonBox.HelpRole)
        self.help_button.clicked.connect(self.mostrar_ayuda)
        # --- FIN DE LA MODIFICACIÓN ---

    # --- INICIO DE LA MODIFICACIÓN ---
    # Nuevo método para mostrar el archivo de ayuda
    def mostrar_ayuda(self):
        """
        Abre el archivo README.html local en el navegador web predeterminado.
        """
        # Construye la ruta al archivo de ayuda
        plugin_dir = os.path.dirname(__file__)
        help_file_path = os.path.join(plugin_dir, 'README.html')

        if os.path.exists(help_file_path):
            # Abre el archivo en el navegador web usando una ruta de archivo URL
            webbrowser.open(f'file:///{os.path.realpath(help_file_path)}')
        else:
            # Muestra un mensaje de advertencia si no se encuentra el archivo
            self.iface.messageBar().pushMessage(
                "Error",
                f"No se pudo encontrar el archivo de ayuda: {help_file_path}",
                level=Qgis.Warning,
                duration=5
            )
    # --- FIN DE LA MODIFICACIÓN ---

    def _conectar_field_comboboxes(self):
        self.mMapLayerComboBox_dro_vias.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dro_direccion.setLayer(layer))
        self.mMapLayerComboBox_dro_vias.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dro_costo.setLayer(layer))
        self.mMapLayerComboBox_dro_puntos.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dro_id_puntos.setLayer(layer))
        self.mMapLayerComboBox_dai_vias.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dai_direccion.setLayer(layer))
        self.mMapLayerComboBox_dai_vias.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dai_costo.setLayer(layer))
        self.mMapLayerComboBox_dai_puntos.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dai_id_puntos.setLayer(layer))
        self.mMapLayerComboBox_dumc_vias.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dumc_direccion.setLayer(layer))
        self.mMapLayerComboBox_dumc_vias.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dumc_costo.setLayer(layer))
        self.mMapLayerComboBox_dumc_puntos1.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dumc_id_puntos1.setLayer(layer))
        self.mMapLayerComboBox_dumc_puntos2.layerChanged.connect(
            lambda layer: self.mFieldComboBox_dumc_id_puntos2.setLayer(layer))

    def _configurar_file_widgets(self):
        widgets_filtros = [
            (self.mFileWidget_dro_salida, "Shapefiles (*.shp)"),
            (self.mFileWidget_dai_salida_lineas, "Shapefiles (*.shp)"),
            (self.mFileWidget_dai_salida_poligono, "Shapefiles (*.shp)"),
            (self.mFileWidget_dumc_salida_puntos, "Shapefiles (*.shp)"),
            (self.mFileWidget_dumc_salida_rutas, "Shapefiles (*.shp)"),
        ]
        for widget, filtro in widgets_filtros:
            widget.setStorageMode(QgsFileWidget.SaveFile)
            widget.setFilter(filtro)

    def _conectar_botones_examinar(self):
        self.mPushButton_dro_vias_browse.clicked.connect(lambda:
                                                          self._examinar_y_cargar_capa(self.mMapLayerComboBox_dro_vias, QgsMapLayerProxyModel.LineLayer))
        self.mPushButton_dro_puntos_browse.clicked.connect(lambda:
                                                            self._examinar_y_cargar_capa(self.mMapLayerComboBox_dro_puntos, QgsMapLayerProxyModel.PointLayer))
        self.mPushButton_dai_vias_browse.clicked.connect(lambda:
                                                          self._examinar_y_cargar_capa(self.mMapLayerComboBox_dai_vias, QgsMapLayerProxyModel.LineLayer))
        self.mPushButton_dai_puntos_browse.clicked.connect(lambda:
                                                            self._examinar_y_cargar_capa(self.mMapLayerComboBox_dai_puntos, QgsMapLayerProxyModel.PointLayer))
        self.mPushButton_dumc_vias_browse.clicked.connect(lambda:
                                                           self._examinar_y_cargar_capa(self.mMapLayerComboBox_dumc_vias, QgsMapLayerProxyModel.LineLayer))
        self.mPushButton_dumc_puntos1_browse.clicked.connect(lambda:
                                                              self._examinar_y_cargar_capa(self.mMapLayerComboBox_dumc_puntos1, QgsMapLayerProxyModel.PointLayer))
        self.mPushButton_dumc_puntos2_browse.clicked.connect(lambda:
                                                              self._examinar_y_cargar_capa(self.mMapLayerComboBox_dumc_puntos2, QgsMapLayerProxyModel.PointLayer))

    def _examinar_y_cargar_capa(self, map_layer_combo_box, layer_type_filter):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Capa", "", "Shapefiles (*.shp);;GeoPackage (*.gpkg);;Todos los archivos (*)")
        if file_path:
            layer_name = os.path.splitext(os.path.basename(file_path))[0]
            layer = QgsVectorLayer(file_path, layer_name, "ogr")
            if not layer.isValid():
                self.iface.messageBar().pushMessage(
                    "Error", f"No se pudo cargar la capa: {file_path}", level=Qgis.Critical, duration=5)
                return
            is_correct_type = False
            geom_type = layer.wkbType()
            base_geom_type = QgsWkbTypes.geometryType(geom_type)
            if layer_type_filter == QgsMapLayerProxyModel.LineLayer and base_geom_type in [QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString]:
                is_correct_type = True
            elif layer_type_filter == QgsMapLayerProxyModel.PointLayer and base_geom_type in [QgsWkbTypes.Point, QgsWkbTypes.MultiPoint]:
                is_correct_type = True
            if not is_correct_type:
                expected_type_str = 'línea' if layer_type_filter == QgsMapLayerProxyModel.LineLayer else 'punto'
                self.iface.messageBar().pushMessage(
                    "Error", f"Tipo de geometría incorrecto para '{file_path}'. Se esperaba {expected_type_str}.", level=Qgis.Critical, duration=5)
                return
            QgsProject.instance().addMapLayer(layer, False)
            map_layer_combo_box.setLayer(layer)

    def actualizar_descripcion_tab(self, index):
        desc_dro = """<b>Determinación de Ruta Óptima (DRO)</b><br>
                      Calcula la ruta más rápida (menor costo) entre pares de puntos sobre una red vial.
                      Se requiere una capa de vías (líneas) con campos que indiquen el costo de desplazamiento y la dirección de la vía.
                      También se necesita una capa de puntos (mínimo 2) con un campo identificador.
                      El algoritmo generará rutas de ida y vuelta para cada par de puntos. Si una ruta no es posible, no se creará.
                      La salida es un archivo de líneas con las rutas óptimas, conteniendo ID de origen, ID de destino y costo acumulado."""
        desc_dai = """<b>Determinación de Área de Influencia (DAI)</b><br>
                      Define el área alcanzable desde uno o más puntos centrales (orígenes) dentro de un umbral de costo (ej. tiempo) especificado.
                      Requiere una capa de vías (costo, dirección), una capa de puntos centrales (mínimo 1) y un valor numérico para el umbral.
                      Se generan todas las rutas de salida posibles desde cada punto central sin superar el umbral.
                      La salida consiste en dos archivos: uno de líneas representando las rutas alcanzables y otro de polígonos que delimitan el área de influencia para cada punto central."""
        desc_dumc = """<b>Determinación de Utilidad Más Cercana (DUMC)</b><br>
                       Para cada punto en una capa de orígenes (Capa Puntos 1), encuentra cuál punto de una capa de destinos/utilidades (Capa Puntos 2) es el más cercano en términos de costo de desplazamiento por la red.
                       Requiere una capa de vías (costo, dirección), una capa de Puntos 1 (mínimo 1 origen) y una capa de Puntos 2 (mínimo 1 utilidad, idealmente más).
                       La salida son dos archivos: uno de puntos que identifica la utilidad más cercana para cada origen, y otro de líneas con las rutas óptimas desde cada origen a su utilidad más cercana encontrada."""
        descriptions = [desc_dro, desc_dai, desc_dumc]
        if 0 <= index < len(descriptions):
            self.textBrowser_descripcion.setHtml(descriptions[index])

    def _validar_entradas_comunes(self, vias_combo, dir_combo, cost_combo):
        vias_layer = vias_combo.currentLayer()
        if not vias_layer:
            self.iface.messageBar().pushMessage(
                "Error", "Capa de vías no seleccionada.", level=Qgis.Critical, duration=3)
            return None, None, None
        dir_field_name = dir_combo.currentField()
        cost_field_name = cost_combo.currentField()
        return vias_layer, dir_field_name, cost_field_name

    def _validar_capa_puntos(self, puntos_combo, id_combo, nombre_capa="Puntos"):
        puntos_layer = puntos_combo.currentLayer()
        if not puntos_layer:
            self.iface.messageBar().pushMessage(
                "Error", f"Capa de {nombre_capa} no seleccionada.", level=Qgis.Critical, duration=3)
            return None, None
        id_field_name = id_combo.currentField()
        if not id_field_name:
            self.iface.messageBar().pushMessage(
                "Error", f"Campo Identificador para {nombre_capa} no seleccionado.", level=Qgis.Critical, duration=3)
            return None, None
        return puntos_layer, id_field_name

    def _manejar_salida(self, widget_salida, nombre_default_temp, check_abrir, tipo_archivo_esperado="shapefile"):
        output_path = widget_salida.filePath()
        if not output_path:
            output_path = f"memory:{nombre_default_temp}"
        elif not output_path.lower().endswith((".shp", ".gpkg")):
            base, ext = os.path.splitext(output_path)
            if tipo_archivo_esperado == "shapefile" and ext.lower() != ".shp":
                output_path = base + ".shp"
        abrir_despues = check_abrir.isChecked()
        return output_path, abrir_despues

    def _cargar_capa_salida(self, layer_or_path, display_name_if_path, abrir_despues_de_ejecutar):
        if not abrir_despues_de_ejecutar or not layer_or_path:
            return

        if isinstance(layer_or_path, QgsVectorLayer):  # Es un objeto QgsVectorLayer (capa de memoria)
            QgsMessageLog.logMessage(
                f"Añadiendo objeto de capa de memoria '{layer_or_path.name()}' al proyecto.", "PluginInfo", Qgis.Info)
            QgsProject.instance().addMapLayer(layer_or_path)
            if self.iface.layerTreeView() and hasattr(self.iface.layerTreeView(), 'setCurrentLayer'):
                self.iface.layerTreeView().setCurrentLayer(layer_or_path)
            if self.iface.mapCanvas():
                self.iface.mapCanvas().refreshAllLayers()

        elif isinstance(layer_or_path, str):  # Es una ruta de archivo (string)
            if layer_or_path.startswith("memory:"):
                QgsMessageLog.logMessage(
                    f"ADVERTENCIA: Se recibió URI de memoria '{layer_or_path}' en lugar de objeto QgsVectorLayer. Intentando cargar...", "PluginWarning", Qgis.Warning)
                loaded_layer = self.iface.addVectorLayer(
                    layer_or_path, display_name_if_path, "memory")
                if not loaded_layer or not loaded_layer.isValid():
                    QgsMessageLog.logMessage(
                        f"FALLO al cargar capa de memoria desde URI: {layer_or_path}", "PluginError", Qgis.Critical)
                    self.iface.messageBar().pushMessage(
                        "Error", f"No se pudo mostrar la capa temporal: {display_name_if_path}", level=Qgis.Critical)
            else:  # Es un archivo en disco
                layer_name_on_load = os.path.splitext(os.path.basename(
                    layer_or_path))[0] if os.path.basename(layer_or_path) else display_name_if_path
                loaded_layer = self.iface.addVectorLayer(
                    layer_or_path, layer_name_on_load, "ogr")
                if not loaded_layer or not loaded_layer.isValid():
                    self.iface.messageBar().pushMessage(
                        "Error", f"No se pudo cargar la capa de salida: {layer_or_path}", level=Qgis.Warning)
        else:
            QgsMessageLog.logMessage(
                f"Tipo de dato no esperado para cargar capa: {type(layer_or_path)}", "PluginError", Qgis.Critical)

    def run_dro(self):
        try:
            vias_layer, dir_field_name, cost_field_name = self._validar_entradas_comunes(
                self.mMapLayerComboBox_dro_vias, self.mFieldComboBox_dro_direccion, self.mFieldComboBox_dro_costo)
            if not vias_layer:
                return

            puntos_layer, id_puntos_field_name = self._validar_capa_puntos(
                self.mMapLayerComboBox_dro_puntos, self.mFieldComboBox_dro_id_puntos, "Puntos (DRO)")
            if not puntos_layer:
                return

            output_path, abrir_despues = self._manejar_salida(
                self.mFileWidget_dro_salida, "rutas_optimas_dro_temp", self.mCheckBox_dro_abrir_salida)

            self.iface.messageBar().pushMessage(
                "Info", "Procesando DRO...", level=Qgis.Info, duration=3)

            success, result_info = network_algorithms.run_dro_analysis_core(
                vias_layer, dir_field_name, cost_field_name,
                puntos_layer, id_puntos_field_name,
                output_path, self.iface
            )

            if success:
                self.iface.messageBar().pushMessage(
                    "Éxito", "Análisis DRO completado.", level=Qgis.Success, duration=5)
                nombre_base = "rutas_optimas_dro_nx" if isinstance(
                    result_info, str) else result_info.name()
                self._cargar_capa_salida(
                    result_info, nombre_base, abrir_despues)
            else:
                self.iface.messageBar().pushMessage(
                    "Error", "Falló el análisis DRO. Revise el Panel de Mensajes de Log.", level=Qgis.Critical, duration=5)

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Excepción en PluginDialog.run_dro: {e}\n{traceback.format_exc()}", "PluginError", Qgis.Critical)
            self.iface.messageBar().pushMessage(
                "Error Crítico", f"Ocurrió una excepción en DRO: {e}", level=Qgis.Critical, duration=10)

    def run_dai(self):
        try:
            vias_layer, dir_field_name, cost_field_name = self._validar_entradas_comunes(
                self.mMapLayerComboBox_dai_vias, self.mFieldComboBox_dai_direccion, self.mFieldComboBox_dai_costo)
            if not vias_layer:
                return

            puntos_layer, id_puntos_field_name = self._validar_capa_puntos(
                self.mMapLayerComboBox_dai_puntos, self.mFieldComboBox_dai_id_puntos, "Puntos Centrales (DAI)")
            if not puntos_layer:
                return

            umbral_costo = self.mDoubleSpinBox_dai_umbral.value()
            if umbral_costo <= 0:
                self.iface.messageBar().pushMessage(
                    "Error", "El umbral de costo debe ser mayor que cero.", level=Qgis.Critical, duration=3)
                return

            output_line_path, abrir_lineas_despues = self._manejar_salida(
                self.mFileWidget_dai_salida_lineas, "dai_lineas_temp", self.mCheckBox_dai_abrir_lineas)
            output_poly_path, abrir_polys_despues = self._manejar_salida(
                self.mFileWidget_dai_salida_poligono, "dai_poligonos_temp", self.mCheckBox_dai_abrir_poligono)

            self.iface.messageBar().pushMessage(
                "Info", "Procesando DAI...", level=Qgis.Info, duration=3)

            success, line_result, poly_result = network_algorithms.run_dai_analysis_core(
                vias_layer, dir_field_name, cost_field_name,
                puntos_layer, id_puntos_field_name, umbral_costo,
                output_line_path, output_poly_path, self.iface
            )

            if success:
                self.iface.messageBar().pushMessage(
                    "Éxito", "Análisis DAI completado.", level=Qgis.Success, duration=5)
                if line_result:
                    nombre_base_lineas = "dai_lineas_nx" if isinstance(
                        line_result, str) else line_result.name()
                    self._cargar_capa_salida(
                        line_result, nombre_base_lineas, abrir_lineas_despues)
                if poly_result:
                    nombre_base_polys = "dai_poligonos_nx" if isinstance(
                        poly_result, str) else poly_result.name()
                    self._cargar_capa_salida(
                        poly_result, nombre_base_polys, abrir_polys_despues)
            else:
                self.iface.messageBar().pushMessage(
                    "Error", "Falló el análisis DAI. Revise el Panel de Mensajes de Log.", level=Qgis.Critical, duration=5)

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Excepción en PluginDialog.run_dai: {e}\n{traceback.format_exc()}", "PluginError", Qgis.Critical)
            self.iface.messageBar().pushMessage(
                "Error Crítico", f"Ocurrió una excepción en DAI: {e}", level=Qgis.Critical, duration=10)

    def run_dumc(self):
        try:
            vias_layer, dir_field_name, cost_field_name = self._validar_entradas_comunes(
                self.mMapLayerComboBox_dumc_vias,
                self.mFieldComboBox_dumc_direccion,
                self.mFieldComboBox_dumc_costo
            )
            if not vias_layer:
                return

            puntos1_layer, id_puntos1_field_name = self._validar_capa_puntos(
                self.mMapLayerComboBox_dumc_puntos1,
                self.mFieldComboBox_dumc_id_puntos1,
                "Puntos 1 (Orígenes DUMC)"
            )
            if not puntos1_layer:
                return

            puntos2_layer, id_puntos2_field_name = self._validar_capa_puntos(
                self.mMapLayerComboBox_dumc_puntos2,
                self.mFieldComboBox_dumc_id_puntos2,
                "Puntos 2 (Utilidades DUMC)"
            )
            if not puntos2_layer:
                return

            output_points_path, abrir_puntos_despues = self._manejar_salida(
                self.mFileWidget_dumc_salida_puntos,
                "dumc_puntos_temp",
                self.mCheckBox_dumc_abrir_puntos
            )
            output_routes_path, abrir_rutas_despues = self._manejar_salida(
                self.mFileWidget_dumc_salida_rutas,
                "dumc_rutas_temp",
                self.mCheckBox_dumc_abrir_rutas
            )

            self.iface.messageBar().pushMessage(
                "Info", "Procesando DUMC...", level=Qgis.Info, duration=3)

            success, points_result, routes_result = network_algorithms.run_dumc_analysis_core(
                vias_layer, dir_field_name, cost_field_name,
                puntos1_layer, id_puntos1_field_name,
                puntos2_layer, id_puntos2_field_name,
                output_points_path, output_routes_path, self.iface
            )

            if success:
                self.iface.messageBar().pushMessage(
                    "Éxito", "Análisis DUMC completado.", level=Qgis.Success, duration=5)
                if points_result:
                    nombre_base_puntos = "dumc_puntos_nx" if isinstance(
                        points_result, str) else points_result.name()
                    self._cargar_capa_salida(
                        points_result, nombre_base_puntos, abrir_puntos_despues)
                if routes_result:
                    nombre_base_rutas = "dumc_rutas_nx" if isinstance(
                        routes_result, str) else routes_result.name()
                    self._cargar_capa_salida(
                        routes_result, nombre_base_rutas, abrir_rutas_despues)
            else:
                self.iface.messageBar().pushMessage(
                    "Error", "Falló el análisis DUMC. Revise el Panel de Mensajes de Log.", level=Qgis.Critical, duration=5)

        except Exception as e:
            detailed_error = traceback.format_exc()
            QgsMessageLog.logMessage(
                f"Excepción en PluginDialog.run_dumc: {e}\n{detailed_error}", "PluginError", Qgis.Critical)
            self.iface.messageBar().pushMessage(
                "Error Crítico", f"Ocurrió una excepción en DUMC: {e}", level=Qgis.Critical, duration=10)