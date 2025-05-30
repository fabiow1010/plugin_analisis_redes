=====================================================
  ANÁLISIS DE REDES DE TRANSPORTE PARA QGIS
=====================================================

QGIS Version: 3.16+

Un plugin para QGIS que provee un conjunto de herramientas potentes y fáciles de usar para realizar análisis de redes de transporte. Ideal para planificadores urbanos, logistas, geógrafos y cualquier profesional que trabaje con datos de redes viales.


*****************************************************
  TABLA DE CONTENIDOS
*****************************************************

1. Descripción General
2. Funcionalidades Principales
3. Requisitos
4. Instalación
5. Guía de Uso
   - Preparación de Datos de Entrada
   - Herramienta 1: Determinación de Ruta Óptima (DRO)
   - Herramienta 2: Determinación de Área de Influencia (DAI)
   - Herramienta 3: Determinación de Utilidad Más Cercana (DUMC)
6. Para Desarrolladores
7. Licencia
8. Autor

-----------------------------------------------------


DESCRIPCIÓN GENERAL
-------------------
Este plugin integra tres de los análisis de redes más comunes directamente en la interfaz de QGIS, permitiendo a los usuarios aprovechar sus propias capas vectoriales para obtener resultados precisos y geográficamente representados. Los algoritmos están construidos sobre librerías robustas como GeoPandas y NetworkX para garantizar un rendimiento y precisión óptimos.


FUNCIONALIDADES PRINCIPALES
---------------------------
- Determinación de Ruta Óptima (DRO): Calcula la ruta más rápida (menor costo) entre múltiples pares de puntos a través de una red vial.
- Determinación de Área de Influencia (DAI): Genera isócronas o áreas de servicio, mostrando qué tan lejos se puede llegar desde un punto central dado un umbral de costo (tiempo o distancia).
- Determinación de Utilidad Más Cercana (DUMC): Para un conjunto de orígenes, identifica cuál de las "utilidades" o destinos disponibles es el más cercano y traza la ruta óptima hacia él.


REQUISITOS
----------
Antes de instalar, asegúrate de cumplir con los siguientes requisitos:

1. QGIS: Versión 3.16 o superior.

2. Librerías de Python: El plugin depende de varias librerías que deben estar instaladas en el ambiente de Python de QGIS.
   - geopandas
   - networkx
   - shapely

   NOTA: Para instalar estas librerías, puedes usar la terminal OSGeo4W Shell que viene con la instalación de QGIS en Windows, o acceder a la consola de Python dentro de QGIS. Un comando típico sería 'pip install geopandas networkx shapely'.


INSTALACIÓN
-----------
Para instalar el plugin desde un repositorio de GitHub, sigue estos pasos:

1. Descarga el repositorio como un archivo ZIP.
2. Descomprime el archivo ZIP. Asegúrate de que la carpeta resultante se llame 'mi_plugin_analisis_redes' (o un nombre similar) y contenga todos los archivos del plugin (.py, .ui, metadata.txt, etc.).
3. Abre QGIS.
4. Ve al menú Complementos > Administrar e instalar complementos...
5. En la ventana de Complementos, selecciona la pestaña 'Instalar desde ZIP'.
6. Haz clic en el botón '...' y navega hasta el archivo ZIP que descargaste.
7. Haz clic en 'Instalar Complemento'.
8. Una vez instalado, asegúrate de que esté habilitado en la pestaña 'Instalados'. Deberías ver un nuevo icono en la barra de herramientas.


=================
  GUÍA DE USO
=================

Al ejecutar el plugin, se abrirá una ventana con tres pestañas en la parte superior: DRO, DAI y DUMC. A la derecha, encontrarás un panel de ayuda que describe la funcionalidad de la pestaña activa.

Preparación de Datos de Entrada
-------------------------------
Para que los algoritmos funcionen correctamente, tus datos deben cumplir con ciertas condiciones.

1. Capa de Vías (Líneas)
   Esta es la capa más importante y debe tener las siguientes características:
   - Conectividad: La red debe estar *correctamente segmentada*. Esto significa que cada tramo de calle entre dos intersecciones debe ser un objeto de línea separado. Donde las líneas se cruzan, debe existir un nodo (un punto de inicio/fin) que las conecte.
   - Atributos / Campos Requeridos:
     - Campo de Costo: Un campo numérico que representa el "costo" de viajar por ese segmento. Generalmente es el *tiempo* (en segundos, minutos, etc.) o la *distancia*. Las unidades deben ser consistentes en toda la capa.
     - Campo de Dirección: Un campo numérico que define la direccionalidad del tráfico, usando los siguientes códigos:
       - 0: Tránsito en *ambos sentidos*.
       - 1: Tránsito solo en el *sentido de la digitalización* (del nodo de inicio al nodo de fin de la línea).
       - 2: Tránsito solo en el *sentido contrario a la digitalización* (del nodo de fin al nodo de inicio).
       - 3: *Restringido*. No se puede transitar por este segmento.

2. Capa de Puntos
   - Ubicación: Los puntos (orígenes, destinos, etc.) deben estar ubicados *sobre los nodos de la capa de vías* (intersecciones o finales de línea). Si un punto no está exactamente sobre un nodo, el algoritmo lo "ajustará" (snap) al nodo más cercano de la red.
   - Atributos / Campos Requeridos:
     - Campo Identificador: Un campo único (puede ser numérico o alfanumérico) que identifique a cada punto.


Herramienta 1: Determinación de Ruta Óptima (DRO)
-------------------------------------------------
Esta herramienta calcula las rutas más rápidas entre cada par de puntos en una capa.

* Entradas:
  1. Capa de Vías: Tu red vial preparada.
  2. Campo Dirección: El campo que define la direccionalidad.
  3. Campo Costo: El campo con el costo de desplazamiento.
  4. Capa de Puntos: Capa con al menos 2 puntos.
  5. Campo Identificador: El ID único para los puntos.
  6. Rutas Óptimas (DRO): La ruta para guardar el archivo de salida. Si se deja en blanco, se creará una capa temporal.

* Salida:
  - Una capa de líneas (.shp) que contiene todas las rutas óptimas calculadas. Sus atributos son:
    - ORIGEN_ID: Identificador del punto de inicio.
    - DESTINO_ID: Identificador del punto de llegada.
    - COSTO_ACC: El costo total acumulado de la ruta.


Herramienta 2: Determinación de Área de Influencia (DAI)
--------------------------------------------------------
Esta herramienta calcula el área de servicio (isócronas) desde uno o más puntos centrales.

* Entradas:
  1. Capa de Vías, Campo Dirección, Campo Costo: Igual que en DRO.
  2. Capa de Puntos (Centrales): Los puntos desde los cuales se calculará el área.
  3. Campo Identificador: El ID único para los puntos centrales.
  4. Umbral de Costo: El valor máximo de costo (ej. 300 segundos para un área de 5 minutos).
  5. Archivos de Salida: Puedes especificar rutas para guardar los resultados de líneas y polígonos. Si se dejan en blanco, se crearán capas temporales.

* Salidas:
  1. Capa de Líneas ('DAI_linea'): Muestra todas las rutas alcanzables desde cada punto central sin exceder el umbral.
     - ORIGEN_ID: El ID del punto central.
     - DEST_NODO_ID: El ID interno del nodo final de la ruta.
     - COSTO_ACC: El costo acumulado de esa ruta específica.
  2. Capa de Polígonos ('DAI_poligono'): Un polígono que une los puntos finales de las rutas para visualizar el área de influencia total.
     - ORIGEN_ID: El ID del punto central asociado al área.
     - UMBRAL: El umbral de costo utilizado.


Herramienta 3: Determinación de Utilidad Más Cercana (DUMC)
-----------------------------------------------------------
Para cada "origen", esta herramienta encuentra el "destino" más cercano y calcula la ruta.

* Entradas:
  1. Capa de Vías, Campo Dirección, Campo Costo: Igual que en DRO.
  2. Capa de Puntos 1 (Orígenes): La capa de puntos desde donde se iniciará la búsqueda.
  3. Capa de Puntos 2 (Utilidades): La capa de posibles destinos.
  4. Archivos de Salida: Rutas para guardar los puntos y las rutas resultantes. Si se dejan en blanco, se crearán capas temporales.

* Salidas:
  1. Capa de Puntos ('DUMC_punto'): Una capa que contiene una copia de los puntos de la capa de Utilidades que resultaron ser los más cercanos para algún origen.
     - ID_ORIGEN: El ID del punto de origen.
     - ID_UTILIDAD: El ID de la utilidad más cercana encontrada.
     - COSTO_MIN: El costo para llegar a esa utilidad.
  2. Capa de Líneas ('DUMC_rutas'): Las rutas óptimas desde cada origen hasta su utilidad más cercana.
     - ID_ORIGEN: El ID del punto de origen.
     - ID_UTILIDAD: El ID de la utilidad de destino.
     - COSTO_RUTA: El costo total de la ruta.


PARA DESARROLLADORES
--------------------
El código fuente está estructurado de la siguiente manera para facilitar su comprensión y mantenimiento.

mi_plugin_analisis_redes/
|-- __init__.py                 # Inicializador del plugin
|-- metadata.txt                # Información del plugin para QGIS
|-- main_plugin.py              # Clase principal, maneja la GUI
|-- plugin_dialog.py            # Lógica y conexiones del diálogo
|-- plugin_dialog_base.ui       # Archivo de interfaz de Qt Designer
|-- network_algorithms.py       # Contiene toda la lógica de análisis geoespacial
|-- icon.png                    # Icono del plugin


LICENCIA
--------
Este proyecto se distribuye bajo la licencia [...]. Ver el archivo LICENSE para más detalles.


AUTOR
-----
- [Cristhian Cante, Fabian Fernandez] - Desarrollo inicial - [cccanteh@udistrital.edu.co, ...]