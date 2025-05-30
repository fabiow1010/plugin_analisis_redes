# -*- coding: utf-8 -*-
import os
import traceback

# --- NUEVAS DEPENDENCIAS EXTERNAS ---
try:
    import geopandas as gpd
    import networkx as nx
    from shapely.geometry import Point, LineString, MultiLineString as ShapelyMultiLineString
except ImportError as e:
    print(f"NETWORK_ALGORITHMS.PY: Error importando librerías (geopandas, networkx, shapely): {e}")
    raise ImportError(f"Librerías (geopandas, networkx, shapely) no encontradas. Instálelas en el entorno Python de QGIS. Error: {e}") from e

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsFields, QgsField, QgsGeometry, QgsPointXY,
    QgsProject, QgsVectorFileWriter, QgsWkbTypes, Qgis, QgsMessageLog,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform
)
from qgis.PyQt.QtCore import QVariant

# --- Funciones Auxiliares de Creación de Capas QGIS (Para archivos en disco) ---
def create_file_writer(path, layer_name_log, fields_structure, geom_type_qgis, crs):
    driver_name = "ESRI Shapefile"
    if path.lower().endswith(".gpkg"):
        driver_name = "GPKG"
    
    writer = QgsVectorFileWriter(path, "UTF-8", fields_structure, geom_type_qgis, crs, driver_name)
    if writer.hasError() != QgsVectorFileWriter.NoError:
        QgsMessageLog.logMessage(f"Error al crear writer para {layer_name_log} en {path}: {writer.errorMessage()}", "AnálisisRedes", Qgis.Critical)
        return None
    return writer

# --- Funciones Auxiliares para Conversión ---
def qgs_feature_to_shapely(qgs_feature, source_crs_qgis, target_crs_qgis=None):
    geom_qgs = qgs_feature.geometry()
    if geom_qgs.isNull() or not geom_qgs.constGet(): return None
    if target_crs_qgis and source_crs_qgis.isValid() and target_crs_qgis.isValid() and \
       source_crs_qgis.authid() != target_crs_qgis.authid():
        transform = QgsCoordinateTransform(source_crs_qgis, target_crs_qgis, QgsProject.instance())
        if transform.isValid(): geom_qgs.transform(transform)
        else: QgsMessageLog.logMessage(f"Transformación CRS inválida para feature {qgs_feature.id()}", "ConversionError", Qgis.Warning); return None
    try:
        wkt = geom_qgs.asWkt()
        geoseries_from_wkt = gpd.GeoSeries.from_wkt([wkt])
        if not geoseries_from_wkt.empty: return geoseries_from_wkt.iloc[0]
        return None
    except Exception as e: QgsMessageLog.logMessage(f"Error convirtiendo QgsGeometry (ID: {qgs_feature.id()}) a Shapely: {e}. WKT: {geom_qgs.asWkt()}", "ConversionError", Qgis.Warning); return None

def shapely_to_qgs_geometry(shapely_geom): 
    if shapely_geom is None or shapely_geom.is_empty: return QgsGeometry()
    try: return QgsGeometry.fromWkt(shapely_geom.wkt)
    except Exception as e: QgsMessageLog.logMessage(f"Error convirtiendo Shapely a QgsGeometry: {e}. WKT: {shapely_geom.wkt}", "ConversionError", Qgis.Warning); return QgsGeometry()

def qgs_layer_to_gdf(qgs_layer, target_crs_qgis=None):
    if not qgs_layer or not qgs_layer.isValid(): QgsMessageLog.logMessage("qgs_layer_to_gdf: Capa inválida.", "GDF_Conversion", Qgis.Critical); return None
    features_data = []; field_names = [field.name() for field in qgs_layer.fields()]
    source_crs_qgis = qgs_layer.crs()
    final_target_crs_qgis = target_crs_qgis if target_crs_qgis and target_crs_qgis.isValid() else source_crs_qgis
    for qgs_feat in qgs_layer.getFeatures():
        shapely_geom = qgs_feature_to_shapely(qgs_feat, source_crs_qgis, final_target_crs_qgis)
        attrs = {name: qgs_feat[name] for name in field_names}
        attrs['_qgs_fid_'] = qgs_feat.id() if qgs_feat.isValid() else None
        attrs['geometry'] = shapely_geom; features_data.append(attrs)
    gdf_crs_wkt = final_target_crs_qgis.toWkt() if final_target_crs_qgis and final_target_crs_qgis.isValid() else None
    if not features_data: return gpd.GeoDataFrame(columns=field_names + ['_qgs_fid_', 'geometry'], crs=gdf_crs_wkt)
    return gpd.GeoDataFrame(features_data, geometry='geometry', crs=gdf_crs_wkt)

_G_nx = None; _nodo_id_map_nx = {}; _id_nodo_counter_nx = 0
_id_to_shapely_point_nx = {}; _vias_gdf_for_snapping_nx = None
_vias_layer_source_path_nx = None; _vias_qgs_crs_obj_cache = None

def _get_or_create_nx_node_id(shapely_point):
    global _id_nodo_counter_nx; key = (round(shapely_point.x, 6), round(shapely_point.y, 6))
    if key not in _nodo_id_map_nx: _nodo_id_map_nx[key] = _id_nodo_counter_nx; _id_to_shapely_point_nx[_id_nodo_counter_nx] = shapely_point; _id_nodo_counter_nx += 1
    return _nodo_id_map_nx[key]

def _snap_to_nearest_vertex_nx(shapely_point_to_snap, list_of_road_shapely_geoms, tolerance=1e-6):
    min_dist_sq = float('inf'); nearest_vertex_as_shapely_point = None
    for road_shapely_geom in list_of_road_shapely_geoms:
        if road_shapely_geom is None or road_shapely_geom.is_empty: continue
        candidate_coords_for_snap = []
        if isinstance(road_shapely_geom, LineString):
            if len(road_shapely_geom.coords) >= 2: candidate_coords_for_snap.extend([road_shapely_geom.coords[0], road_shapely_geom.coords[-1]])
        elif isinstance(road_shapely_geom, ShapelyMultiLineString):
            for part_linestring in road_shapely_geom.geoms:
                if len(part_linestring.coords) >= 2: candidate_coords_for_snap.extend([part_linestring.coords[0], part_linestring.coords[-1]])
        for coord_tuple in candidate_coords_for_snap:
            vertex_pt = Point(coord_tuple); dx = shapely_point_to_snap.x - vertex_pt.x
            dy = shapely_point_to_snap.y - vertex_pt.y; dist_sq = dx*dx + dy*dy
            if dist_sq < min_dist_sq: min_dist_sq = dist_sq; nearest_vertex_as_shapely_point = vertex_pt
    if nearest_vertex_as_shapely_point and min_dist_sq < (tolerance * tolerance): return nearest_vertex_as_shapely_point
    return shapely_point_to_snap

def _build_or_get_networkx_graph(vias_qgs_layer, dir_field_name, cost_field_name, force_rebuild=False):
    global _G_nx, _nodo_id_map_nx, _id_nodo_counter_nx, _id_to_shapely_point_nx, \
           _vias_gdf_for_snapping_nx, _vias_layer_source_path_nx, _vias_qgs_crs_obj_cache
    current_vias_source = vias_qgs_layer.source()
    if not force_rebuild and _G_nx is not None and _vias_layer_source_path_nx == current_vias_source:
        QgsMessageLog.logMessage("Reutilizando grafo NetworkX y GDF.", "NetworkX_Cache", Qgis.Info)
        return _G_nx, _vias_gdf_for_snapping_nx, _vias_qgs_crs_obj_cache

    QgsMessageLog.logMessage(f"Construyendo nuevo grafo NetworkX para: {current_vias_source}", "NetworkX_Build", Qgis.Info)
    _G_nx = nx.DiGraph(); _nodo_id_map_nx = {}; _id_nodo_counter_nx = 0; _id_to_shapely_point_nx = {}
    _vias_qgs_crs_obj_cache = vias_qgs_layer.crs()
    vias_gdf = qgs_layer_to_gdf(vias_qgs_layer, target_crs_qgis=_vias_qgs_crs_obj_cache)
    if vias_gdf is None or vias_gdf.empty: QgsMessageLog.logMessage("Capa de vías vacía o inválida para GDF.", "NetworkX_Build", Qgis.Critical); _G_nx = None; return None, None, None
    _vias_gdf_for_snapping_nx = vias_gdf; _vias_layer_source_path_nx = current_vias_source

    for _, row_via in vias_gdf.iterrows():
        geom_via = row_via.geometry; feature_id_for_log = row_via.get('_qgs_fid_', f"ÍndiceGDF_{_}")
        if geom_via is None or geom_via.is_empty: continue
        parts_coords_list = []
        if isinstance(geom_via, LineString):
            if len(geom_via.coords) >= 2: parts_coords_list.append(list(geom_via.coords))
            else: QgsMessageLog.logMessage(f"Vía FID {feature_id_for_log} (LineString): < 2 coords, omitiendo para nodos.", "NetworkX_Build", Qgis.Warning)
        elif isinstance(geom_via, ShapelyMultiLineString):
            for part_idx, part_linestring in enumerate(geom_via.geoms):
                if len(part_linestring.coords) >= 2: parts_coords_list.append(list(part_linestring.coords))
                else: QgsMessageLog.logMessage(f"Vía FID {feature_id_for_log}, parte {part_idx} de MultiLineString: < 2 coords, omitiendo para nodos.", "NetworkX_Build", Qgis.Warning)
        else: QgsMessageLog.logMessage(f"Vía FID {feature_id_for_log}: Geometría no es LineString ni MultiLineString ({type(geom_via)}), omitiendo para nodos.", "NetworkX_Build", Qgis.Warning); continue
        for line_coords in parts_coords_list: _get_or_create_nx_node_id(Point(line_coords[0])); _get_or_create_nx_node_id(Point(line_coords[-1]))
    
    for _, row_via in vias_gdf.iterrows():
        geom_via = row_via.geometry; feature_id_for_log = row_via.get('_qgs_fid_', f"ÍndiceGDF_{_}")
        if geom_via is None or geom_via.is_empty: continue
        cost_val_attr = row_via.get(cost_field_name); direction_attr = row_via.get(dir_field_name)
        direction_to_compare = "0"
        if direction_attr is not None:
            try: direction_to_compare = str(int(float(direction_attr)))
            except (ValueError, TypeError): QgsMessageLog.logMessage(f"Vía FID {feature_id_for_log}: Dirección '{direction_attr}' inválida, usando '0'.", "NetworkX_Build", Qgis.Warning)
        
        edge_geoms_parts = [];
        if isinstance(geom_via, LineString):
            if len(geom_via.coords) >= 2: edge_geoms_parts.append(geom_via)
        elif isinstance(geom_via, ShapelyMultiLineString):
            for part in geom_via.geoms:
                if len(part.coords) >= 2: edge_geoms_parts.append(part)
        if not edge_geoms_parts: continue

        for edge_geom_part in edge_geoms_parts:
            current_edge_cost = edge_geom_part.length if cost_val_attr is None else 0.0
            if cost_val_attr is not None:
                try: cost = float(cost_val_attr); current_edge_cost = cost if cost > 0 else 0.00001
                except (ValueError, TypeError): current_edge_cost = edge_geom_part.length; QgsMessageLog.logMessage(f"Vía FID {feature_id_for_log}: Costo '{cost_val_attr}' no numérico, usando longitud de parte ({current_edge_cost:.2f}).", "NetworkX_Build", Qgis.Warning)
            else: current_edge_cost = edge_geom_part.length; QgsMessageLog.logMessage(f"Vía FID {feature_id_for_log}: Campo de costo ('{cost_field_name}') no encontrado o nulo, usando longitud de parte ({current_edge_cost:.2f}).", "NetworkX_Build", Qgis.Info)
            if current_edge_cost <= 0: current_edge_cost = 0.00001
            
            start_pt = Point(edge_geom_part.coords[0]); end_pt = Point(edge_geom_part.coords[-1])
            u_id = _get_or_create_nx_node_id(start_pt); v_id = _get_or_create_nx_node_id(end_pt)
            if u_id == v_id: continue

            if direction_to_compare == "1": _G_nx.add_edge(u_id, v_id, geometry=edge_geom_part, weight=current_edge_cost)
            elif direction_to_compare == "2": _G_nx.add_edge(v_id, u_id, geometry=LineString(edge_geom_part.coords[::-1]), weight=current_edge_cost)
            elif direction_to_compare == "0": _G_nx.add_edge(u_id, v_id, geometry=edge_geom_part, weight=current_edge_cost); _G_nx.add_edge(v_id, u_id, geometry=LineString(edge_geom_part.coords[::-1]), weight=current_edge_cost)
            elif direction_to_compare != "3": QgsMessageLog.logMessage(f"Vía FID {feature_id_for_log}: Dirección '{direction_to_compare}' no reconocida. Omitida.", "NetworkX_Build", Qgis.Warning)
            
    QgsMessageLog.logMessage(f"Grafo NetworkX construido. Nodos: {_G_nx.number_of_nodes()}, Aristas: {_G_nx.number_of_edges()}", "NetworkX_Build", Qgis.Success)
    return _G_nx, _vias_gdf_for_snapping_nx, _vias_qgs_crs_obj_cache


# --- Lógica de DRO ---
def run_dro_analysis_core(vias_qgs_layer, dir_field_name, cost_field_name,
                          puntos_qgs_layer, id_puntos_field_name,
                          output_path, iface):
    global _G_nx, _id_to_shapely_point_nx 
    
    writer = None 
    output_layer_object = None
    try:
        if 'gpd' not in globals() or 'nx' not in globals():
            err_msg = "Geopandas/NetworkX no instalados."; QgsMessageLog.logMessage(err_msg, "PluginError", Qgis.Critical)
            iface.messageBar().pushMessage("Error Dependencia", err_msg, level=Qgis.Critical); return False, None

        G, vias_gdf_for_snapping, vias_qgs_crs = _build_or_get_networkx_graph(vias_qgs_layer, dir_field_name, cost_field_name, force_rebuild=True)
        if G is None: return False, None

        out_fields_qgis = QgsFields()
        out_fields_qgis.append(QgsField("ORIGEN_ID", QVariant.String)); out_fields_qgis.append(QgsField("DESTINO_ID", QVariant.String))
        out_fields_qgis.append(QgsField("COSTO_ACC", QVariant.Double))
        
        is_memory_output = output_path.startswith("memory:")
        dp = None

        if is_memory_output:
            uri_parts = output_path.split(':', 1); layer_name = uri_parts[1] if len(uri_parts)>1 else "rutas_optimas_temp"
            crs_str = vias_qgs_crs.authid()
            memory_uri_schema = f"LineString?crs={crs_str}"
            for field in out_fields_qgis: memory_uri_schema += f"&field={field.name()}:{QVariant.typeToName(field.type())}({field.length() if field.length() > 0 else 255})"
            
            output_layer_object = QgsVectorLayer(memory_uri_schema, layer_name, "memory")
            if not output_layer_object.isValid(): QgsMessageLog.logMessage(f"Error creando capa memoria DRO: {layer_name}", "PluginError", Qgis.Critical); return False, None
            dp = output_layer_object.dataProvider(); output_layer_object.startEditing()
        else:
            writer = create_file_writer(output_path, "rutas_optimas_dro_nx", out_fields_qgis, QgsWkbTypes.LineString, vias_qgs_crs)
            if not writer: return False, None

        puntos_gdf = qgs_layer_to_gdf(puntos_qgs_layer, target_crs_qgis=vias_qgs_crs)
        if puntos_gdf is None or puntos_gdf.empty: QgsMessageLog.logMessage("DRO: Capa de puntos vacía.", "PluginError", Qgis.Warning) 
        
        map_original_id_to_nx_id = {}; processed_point_ids_in_graph = []
        # Usar la columna de geometría del GeoDataFrame de vías para el snapping
        road_geoms_for_snap = vias_gdf_for_snapping['geometry'].tolist() if vias_gdf_for_snapping is not None else []


        if puntos_gdf is not None and not puntos_gdf.empty:
            for _, row_punto in puntos_gdf.iterrows():
                try: original_id = str(row_punto[id_puntos_field_name])
                except KeyError: 
                    QgsMessageLog.logMessage(f"DRO: Campo ID '{id_puntos_field_name}' no en puntos.", "PluginError", Qgis.Critical)
                    if writer is not None: del writer # Limpieza
                    return False, None
                shapely_point_original = row_punto.geometry
                if not shapely_point_original or shapely_point_original.is_empty: continue
                snapped_point_shapely = _snap_to_nearest_vertex_nx(shapely_point_original, road_geoms_for_snap)
                nx_node_id = _get_or_create_nx_node_id(snapped_point_shapely)
                if not G.has_node(nx_node_id): QgsMessageLog.logMessage(f"DRO: Punto ID '{original_id}' (nodo NX {nx_node_id}) no en grafo.", "PluginWarning", Qgis.Warning); continue
                map_original_id_to_nx_id[original_id] = nx_node_id
                if original_id not in processed_point_ids_in_graph: processed_point_ids_in_graph.append(original_id)

        if len(processed_point_ids_in_graph) < 2: 
            QgsMessageLog.logMessage("DRO: Menos de 2 puntos válidos/mapeados.", "PluginError", Qgis.Warning)
            if writer is not None: del writer # Limpieza
            # Si es capa de memoria, no hay 'writer' que borrar aquí, se devuelve None
            return False, None
            
        rutas_calculadas_count = 0
        for i in range(len(processed_point_ids_in_graph)):
            for j in range(len(processed_point_ids_in_graph)):
                if i == j: continue
                orig_id_str = processed_point_ids_in_graph[i]; dest_id_str = processed_point_ids_in_graph[j]
                source_node = map_original_id_to_nx_id.get(orig_id_str); target_node = map_original_id_to_nx_id.get(dest_id_str)
                if source_node is None or target_node is None or not G.has_node(source_node) or not G.has_node(target_node): continue
                try:
                    path_data = nx.single_source_dijkstra(G, source_node, target=target_node, weight='weight')
                    total_cost, path_nx_nodes = path_data[0], path_data[1]
                    route_coords = []
                    if len(path_nx_nodes) >= 2:
                        for k_idx in range(len(path_nx_nodes) - 1):
                            u_n, v_n = path_nx_nodes[k_idx], path_nx_nodes[k_idx+1]; edge_data = G.get_edge_data(u_n, v_n)
                            if edge_data and "geometry" in edge_data:
                                edge_s_geom = edge_data["geometry"]
                                if not route_coords: route_coords.extend(list(edge_s_geom.coords))
                                else: route_coords.extend(list(edge_s_geom.coords)[1:])
                            else: route_coords = []; QgsMessageLog.logMessage(f"DRO: Falta geometría en arista {u_n}-{v_n} para ruta {orig_id_str}->{dest_id_str}", "PluginWarning", Qgis.Warning); break 
                    if route_coords and len(route_coords) >=2:
                        route_s_geom = LineString(route_coords); route_q_geom = shapely_to_qgs_geometry(route_s_geom)
                        feat = QgsFeature(out_fields_qgis); feat.setGeometry(route_q_geom); feat.setAttributes([orig_id_str, dest_id_str, total_cost])
                        if is_memory_output and dp: dp.addFeature(feat)
                        elif writer: writer.addFeature(feat)
                        rutas_calculadas_count +=1
                except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError): continue
        
        if is_memory_output and output_layer_object: 
            output_layer_object.commitChanges(); output_layer_object.updateExtents()
        elif writer is not None: 
            del writer; writer = None 

        if rutas_calculadas_count > 0: return True, output_layer_object if is_memory_output else output_path
        else: 
            QgsMessageLog.logMessage("DRO (NX) finalizado, no se generaron rutas.", "PluginWarning", Qgis.Warning)
            # Limpiar capa de memoria si no se generaron rutas
            if is_memory_output and output_layer_object is not None:
                # No hay una forma directa de "borrar" un objeto QgsVectorLayer que no se añadió al proyecto.
                # Simplemente no lo devolvemos.
                pass
            return False, None

    except ImportError as e_imp:
        err_msg = f"ImportError: {e_imp}."; QgsMessageLog.logMessage(err_msg, "PluginError", Qgis.Critical)
        iface.messageBar().pushMessage("Error Dependencia", err_msg, level=Qgis.Critical); return False, None
    except Exception as e:
        QgsMessageLog.logMessage(f"Error en run_dro_analysis_core (NX): {e}\n{traceback.format_exc()}", "PluginError", Qgis.Critical)
        if 'writer' in locals() and writer is not None: # CORREGIDO
            try: del writer
            except Exception as e_del: QgsMessageLog.logMessage(f"Excepción menor al intentar 'del writer' en DRO except: {e_del}", "PluginDebug", Qgis.Debug)
        if output_path and os.path.exists(output_path) and not output_path.startswith("memory:"):
             try: os.remove(output_path)
             except Exception as e_rem: QgsMessageLog.logMessage(f"No se pudo borrar {output_path}: {e_rem}", "FileError", Qgis.Warning)
        return False, None

# --- Lógica de DAI ---
def run_dai_analysis_core(vias_qgs_layer, dir_field_name, cost_field_name,
                          puntos_qgs_layer, id_puntos_field_name, umbral_costo,
                          output_line_path, output_poly_path, iface):
    global _G_nx, _id_to_shapely_point_nx
    line_writer, poly_writer = None, None; line_layer_obj, poly_layer_obj = None, None
    dp_line, dp_poly = None, None
    try:
        if 'gpd' not in globals() or 'nx' not in globals():
            err_msg = "Geopandas/NetworkX no instalados."; QgsMessageLog.logMessage(err_msg, "PluginError", Qgis.Critical)
            iface.messageBar().pushMessage("Error Dependencia", err_msg, level=Qgis.Critical); return False, None, None

        G, vias_gdf, vias_qgs_crs = _build_or_get_networkx_graph(vias_qgs_layer, dir_field_name, cost_field_name, force_rebuild=True)
        if G is None: return False, None, None
            
        out_line_fields = QgsFields(); out_line_fields.append(QgsField("ORIGEN_ID", QVariant.String))
        out_line_fields.append(QgsField("DEST_NODO_ID", QVariant.Int)); out_line_fields.append(QgsField("COSTO_ACC", QVariant.Double))
        out_poly_fields = QgsFields(); out_poly_fields.append(QgsField("ORIGEN_ID", QVariant.String)); out_poly_fields.append(QgsField("UMBRAL", QVariant.Double))

        is_mem_line = output_line_path.startswith("memory:")
        is_mem_poly = output_poly_path.startswith("memory:")

        if is_mem_line:
            uri_parts = output_line_path.split(':', 1); name = uri_parts[1] if len(uri_parts)>1 else "dai_lineas_temp"
            uri_schema = f"LineString?crs={vias_qgs_crs.authid()}"
            for fld in out_line_fields: uri_schema += f"&field={fld.name()}:{QVariant.typeToName(fld.type())}({fld.length() if fld.length() > 0 else 255})"
            line_layer_obj = QgsVectorLayer(uri_schema, name, "memory")
            if not line_layer_obj.isValid(): return False, None, None
            dp_line = line_layer_obj.dataProvider(); line_layer_obj.startEditing()
        else:
            line_writer = create_file_writer(output_line_path, "dai_lineas_nx", out_line_fields, QgsWkbTypes.LineString, vias_qgs_crs)
            if not line_writer: return False, None, None

        if is_mem_poly:
            uri_parts = output_poly_path.split(':', 1); name = uri_parts[1] if len(uri_parts)>1 else "dai_polys_temp"
            uri_schema = f"Polygon?crs={vias_qgs_crs.authid()}"
            for fld in out_poly_fields: uri_schema += f"&field={fld.name()}:{QVariant.typeToName(fld.type())}({fld.length() if fld.length() > 0 else 255})"
            poly_layer_obj = QgsVectorLayer(uri_schema, name, "memory")
            if not poly_layer_obj.isValid(): return False, None, None
            dp_poly = poly_layer_obj.dataProvider(); poly_layer_obj.startEditing()
        else:
            poly_writer = create_file_writer(output_poly_path, "dai_poligonos_nx", out_poly_fields, QgsWkbTypes.Polygon, vias_qgs_crs)
            if not poly_writer: 
                if 'line_writer' in locals() and line_writer is not None: del line_writer # Corrected syntax
                return False, None, None
        
        puntos_gdf = qgs_layer_to_gdf(puntos_qgs_layer, target_crs_qgis=vias_qgs_crs)
        if puntos_gdf is None or puntos_gdf.empty: return False, None, None 
        
        road_geoms_for_snap = vias_gdf['geometry'].tolist() if vias_gdf is not None else []


        for _, row_origen in puntos_gdf.iterrows():
            original_id_origen = str(row_origen[id_puntos_field_name])
            shapely_point_origen = row_origen.geometry
            if not shapely_point_origen or shapely_point_origen.is_empty: continue
            snapped_origen_shapely = _snap_to_nearest_vertex_nx(shapely_point_origen, road_geoms_for_snap)
            source_nx_node = _get_or_create_nx_node_id(snapped_origen_shapely)
            if not G.has_node(source_nx_node): continue
            try: costs_from_source, paths_from_source = nx.single_source_dijkstra(G, source_nx_node, cutoff=umbral_costo, weight='weight')
            except nx.NodeNotFound: continue
            
            reachable_path_endpoints_shapely = []
            for target_node_id, cost_to_target in costs_from_source.items():
                path_nx_nodes = paths_from_source.get(target_node_id)
                if not path_nx_nodes: 
                    continue
                route_coords = []
                if len(path_nx_nodes) >= 2:
                    for k_idx in range(len(path_nx_nodes) - 1):
                        u_n, v_n = path_nx_nodes[k_idx], path_nx_nodes[k_idx+1]; edge_data = G.get_edge_data(u_n, v_n)
                        if edge_data and "geometry" in edge_data:
                            edge_s_geom = edge_data["geometry"]
                            if not route_coords: route_coords.extend(list(edge_s_geom.coords))
                            else: route_coords.extend(list(edge_s_geom.coords)[1:])
                        else: route_coords = []; break
                    if route_coords and len(route_coords) >=2:
                        route_s_geom = LineString(route_coords); route_q_geom = shapely_to_qgs_geometry(route_s_geom)
                        feat = QgsFeature(out_line_fields); feat.setGeometry(route_q_geom); feat.setAttributes([original_id_origen, target_node_id, cost_to_target])
                        if is_mem_line and dp_line: dp_line.addFeature(feat)
                        elif line_writer: line_writer.addFeature(feat)
                        if target_node_id in _id_to_shapely_point_nx: reachable_path_endpoints_shapely.append(_id_to_shapely_point_nx[target_node_id])
                        elif path_nx_nodes and route_coords: reachable_path_endpoints_shapely.append(Point(route_coords[-1]))
                elif len(path_nx_nodes) == 1 and source_nx_node == target_node_id: 
                    if source_nx_node in _id_to_shapely_point_nx: reachable_path_endpoints_shapely.append(_id_to_shapely_point_nx[source_nx_node])
            
            if len(reachable_path_endpoints_shapely) >= 3:
                points_for_hull = [p for p in reachable_path_endpoints_shapely if p and not p.is_empty]
                if len(points_for_hull) >=3:
                    from shapely.geometry import MultiPoint as ShapelyMultiPoint
                    hull_input_geom = ShapelyMultiPoint(points_for_hull)
                    if not hull_input_geom.is_empty:
                        convex_hull_geom = hull_input_geom.convex_hull
                        if not convex_hull_geom.is_empty and convex_hull_geom.geom_type == 'Polygon':
                            poly_q_geom = shapely_to_qgs_geometry(convex_hull_geom)
                            feat = QgsFeature(out_poly_fields); feat.setGeometry(poly_q_geom); feat.setAttributes([original_id_origen, umbral_costo])
                            if is_mem_poly and dp_poly: dp_poly.addFeature(feat)
                            elif poly_writer: poly_writer.addFeature(feat)
            # ... (buffer para < 3 puntos) ...

        if is_mem_line and line_layer_obj: line_layer_obj.commitChanges(); line_layer_obj.updateExtents()
        elif line_writer is not None: del line_writer; line_writer = None
        if is_mem_poly and poly_layer_obj: poly_layer_obj.commitChanges(); poly_layer_obj.updateExtents()
        elif poly_writer is not None: del poly_writer; poly_writer = None
        
        QgsMessageLog.logMessage("DAI (NX) completado.", "PluginSuccess", Qgis.Success)
        return True, line_layer_obj if is_mem_line else output_line_path, poly_layer_obj if is_mem_poly else output_poly_path
    except ImportError as e_imp:
        err_msg = f"ImportError: {e_imp}."; QgsMessageLog.logMessage(err_msg, "PluginError", Qgis.Critical)
        iface.messageBar().pushMessage("Error Dependencia", err_msg, level=Qgis.Critical); return False, None, None
    except Exception as e:
        QgsMessageLog.logMessage(f"Error en DAI (NX): {e}\n{traceback.format_exc()}", "PluginError", Qgis.Critical)
        if 'line_writer' in locals() and line_writer is not None: 
            try: del line_writer
            except Exception as e_del: QgsMessageLog.logMessage(f"Excepción menor al 'del line_writer' en DAI except: {e_del}", "PluginDebug", Qgis.Debug)
        if 'poly_writer' in locals() and poly_writer is not None: 
            try: del poly_writer
            except Exception as e_del: QgsMessageLog.logMessage(f"Excepción menor al 'del poly_writer' en DAI except: {e_del}", "PluginDebug", Qgis.Debug)
        # ... (borrado de archivos parciales) ...
        return False, None, None

# --- Lógica de DUMC ---
def run_dumc_analysis_core(vias_qgs_layer, dir_field_name, cost_field_name,
                           puntos1_qgs_layer, id_puntos1_field_name, 
                           puntos2_qgs_layer, id_puntos2_field_name, 
                           output_points_path, output_routes_path, iface):
    global _G_nx, _id_to_shapely_point_nx
    points_writer, routes_writer = None, None; points_layer_obj, routes_layer_obj = None, None
    dp_points, dp_routes = None, None
    try:
        if 'gpd' not in globals() or 'nx' not in globals():
            err_msg = "Geopandas/NetworkX no instalados."; QgsMessageLog.logMessage(err_msg, "PluginError", Qgis.Critical)
            iface.messageBar().pushMessage("Error Dependencia", err_msg, level=Qgis.Critical); return False, None, None

        G, vias_gdf, vias_qgs_crs = _build_or_get_networkx_graph(vias_qgs_layer, dir_field_name, cost_field_name, force_rebuild=True)
        if G is None: return False, None, None
        
        out_points_fields = QgsFields(); out_points_fields.append(QgsField("ID_ORIGEN", QVariant.String))
        out_points_fields.append(QgsField("ID_UTILIDAD", QVariant.String)); out_points_fields.append(QgsField("COSTO_MIN", QVariant.Double))
        out_routes_fields = QgsFields(); out_routes_fields.append(QgsField("ID_ORIGEN", QVariant.String))
        out_routes_fields.append(QgsField("ID_UTILIDAD", QVariant.String)); out_routes_fields.append(QgsField("COSTO_RUTA", QVariant.Double))

        is_mem_points = output_points_path.startswith("memory:")
        is_mem_routes = output_routes_path.startswith("memory:")

        if is_mem_points:
            uri_parts = output_points_path.split(':', 1); name = uri_parts[1] if len(uri_parts)>1 else "dumc_puntos_temp"
            uri_schema = f"Point?crs={vias_qgs_crs.authid()}"
            for fld in out_points_fields: uri_schema += f"&field={fld.name()}:{QVariant.typeToName(fld.type())}({fld.length() if fld.length() > 0 else 255})"
            points_layer_obj = QgsVectorLayer(uri_schema, name, "memory")
            if not points_layer_obj.isValid(): return False, None, None
            dp_points = points_layer_obj.dataProvider(); points_layer_obj.startEditing()
        else:
            points_writer = create_file_writer(output_points_path, "dumc_puntos_nx", out_points_fields, QgsWkbTypes.Point, vias_qgs_crs)
            if not points_writer: return False, None, None
        
        if is_mem_routes:
            uri_parts = output_routes_path.split(':', 1); name = uri_parts[1] if len(uri_parts)>1 else "dumc_rutas_temp"
            uri_schema = f"LineString?crs={vias_qgs_crs.authid()}"
            for fld in out_routes_fields: uri_schema += f"&field={fld.name()}:{QVariant.typeToName(fld.type())}({fld.length() if fld.length() > 0 else 255})"
            routes_layer_obj = QgsVectorLayer(uri_schema, name, "memory")
            if not routes_layer_obj.isValid(): 
                if points_writer is not None: del points_writer # Limpieza
                return False, None, None
            dp_routes = routes_layer_obj.dataProvider(); routes_layer_obj.startEditing()
        else:
            routes_writer = create_file_writer(output_routes_path, "dumc_rutas_nx", out_routes_fields, QgsWkbTypes.LineString, vias_qgs_crs)
            if not routes_writer: 
                if points_writer is not None: del points_writer 
                return False, None, None

        puntos2_gdf = qgs_layer_to_gdf(puntos2_qgs_layer, target_crs_qgis=vias_qgs_crs)
        if puntos2_gdf is None or puntos2_gdf.empty: return False, None, None 
        
        snapped_utilidades_info = []
        road_geoms_for_snap = vias_gdf['geometry'].tolist() if vias_gdf is not None else []
        for _, row_util in puntos2_gdf.iterrows():
            original_id_util = str(row_util[id_puntos2_field_name])
            shapely_point_util = row_util.geometry
            if not shapely_point_util or shapely_point_util.is_empty: continue
            snapped_util_shapely = _snap_to_nearest_vertex_nx(shapely_point_util, road_geoms_for_snap)
            util_nx_node_id = _get_or_create_nx_node_id(snapped_util_shapely)
            if G.has_node(util_nx_node_id): snapped_utilidades_info.append((original_id_util, util_nx_node_id, shapely_point_util))
            else: QgsMessageLog.logMessage(f"DUMC: Utilidad '{original_id_util}' no en grafo.", "PluginWarning", Qgis.Warning)
        
        if not snapped_utilidades_info: return False, None, None 

        puntos1_gdf = qgs_layer_to_gdf(puntos1_qgs_layer, target_crs_qgis=vias_qgs_crs)
        if puntos1_gdf is None or puntos1_gdf.empty: return False, None, None

        for _, row_origen in puntos1_gdf.iterrows():
            original_id_origen = str(row_origen[id_puntos1_field_name])
            shapely_point_origen = row_origen.geometry
            if not shapely_point_origen or shapely_point_origen.is_empty: continue
            snapped_origen_shapely = _snap_to_nearest_vertex_nx(shapely_point_origen, road_geoms_for_snap)
            source_nx_node_origen = _get_or_create_nx_node_id(snapped_origen_shapely)
            if not G.has_node(source_nx_node_origen): continue

            min_costo_actual = float('inf'); mejor_utilidad_id_str = None; mejor_utilidad_s_geom = None; mejor_ruta_s_geom = None
            for util_orig_id_str, util_nx_node_id, util_s_geom_original in snapped_utilidades_info:
                try:
                    if source_nx_node_origen == util_nx_node_id: current_cost = 0.0; path_nx_nodes = [source_nx_node_origen]
                    elif not G.has_node(util_nx_node_id): continue
                    else:
                        path_data = nx.single_source_dijkstra(G, source_nx_node_origen, target=util_nx_node_id, weight='weight')
                        current_cost, path_nx_nodes = path_data[0], path_data[1]
                    if current_cost < min_costo_actual:
                        min_costo_actual = current_cost; mejor_utilidad_id_str = util_orig_id_str; mejor_utilidad_s_geom = util_s_geom_original
                        route_coords = []
                        if len(path_nx_nodes) >= 2:
                            for k_idx in range(len(path_nx_nodes) - 1):
                                u_n, v_n = path_nx_nodes[k_idx], path_nx_nodes[k_idx+1]; edge_data = G.get_edge_data(u_n, v_n)
                                if edge_data and "geometry" in edge_data:
                                    edge_s_geom = edge_data["geometry"]
                                    if not route_coords: route_coords.extend(list(edge_s_geom.coords))
                                    else: route_coords.extend(list(edge_s_geom.coords)[1:])
                                else: route_coords = []; break
                            if route_coords: mejor_ruta_s_geom = LineString(route_coords)
                        elif len(path_nx_nodes) == 1: mejor_ruta_s_geom = snapped_origen_shapely 
                except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError): continue
            
            if mejor_utilidad_id_str is not None:
                feat_pt = QgsFeature(out_points_fields); feat_pt.setGeometry(shapely_to_qgs_geometry(mejor_utilidad_s_geom))
                feat_pt.setAttributes([original_id_origen, mejor_utilidad_id_str, min_costo_actual])
                if is_mem_points and dp_points: dp_points.addFeature(feat_pt)
                elif points_writer: points_writer.addFeature(feat_pt)
                
                if mejor_ruta_s_geom and not mejor_ruta_s_geom.is_empty:
                    feat_rt = QgsFeature(out_routes_fields); feat_rt.setGeometry(shapely_to_qgs_geometry(mejor_ruta_s_geom))
                    feat_rt.setAttributes([original_id_origen, mejor_utilidad_id_str, min_costo_actual])
                    if is_mem_routes and dp_routes: dp_routes.addFeature(feat_rt)
                    elif routes_writer: routes_writer.addFeature(feat_rt)

        if is_mem_points and points_layer_obj: points_layer_obj.commitChanges(); points_layer_obj.updateExtents()
        elif points_writer is not None: del points_writer; points_writer = None
        if is_mem_routes and routes_layer_obj: routes_layer_obj.commitChanges(); routes_layer_obj.updateExtents()
        elif routes_writer is not None: del routes_writer; routes_writer = None
        
        QgsMessageLog.logMessage("Análisis DUMC (NetworkX) completado.", "PluginSuccess", Qgis.Success)
        return True, points_layer_obj if is_mem_points else output_points_path, routes_layer_obj if is_mem_routes else output_routes_path
        
    except ImportError as e_imp:
        err_msg = f"ImportError: {e_imp}."; QgsMessageLog.logMessage(err_msg, "PluginError", Qgis.Critical)
        iface.messageBar().pushMessage("Error Dependencia", err_msg, level=Qgis.Critical); return False, None, None
    except Exception as e:
        QgsMessageLog.logMessage(f"Error en DUMC (NX): {e}\n{traceback.format_exc()}", "PluginError", Qgis.Critical)
        if 'points_writer' in locals() and points_writer is not None: 
            try: del points_writer
            except Exception as e_del: QgsMessageLog.logMessage(f"Excepción menor al 'del points_writer' en DUMC except: {e_del}", "PluginDebug", Qgis.Debug)
        if 'routes_writer' in locals() and routes_writer is not None: 
            try: del routes_writer
            except Exception as e_del: QgsMessageLog.logMessage(f"Excepción menor al 'del routes_writer' en DUMC except: {e_del}", "PluginDebug", Qgis.Debug)
        return False, None, None