"""
slicer.py
---------
Corte de malla STL en capas y generación de rutas de herramienta (toolpaths)
optimizadas para impresión/extrusión con brazo robótico.

Cambios respecto a la versión anterior:
- Se eliminaron imports no usados (plotly, webbrowser, os, json, matplotlib,
  y las funciones de visualizadores que no se usan dentro de este módulo).
- Se unificó la lógica de "vecino más cercano", que estaba duplicada en
  optimize_layer_path() y optimize_all_layers_path(), en una sola función
  reutilizable: _nearest_neighbor_order().
- Se agregó el filtro is_valid / is_empty (ya usado en stl_to_path.py) para
  descartar polígonos inválidos/auto-intersectados que provocan que la ruta
  "salte" de un lado a otro dentro del mismo contorno. Ver explicación en el
  chat (Shapely explain_validity -> "Ring Self-intersection").
- _nearest_neighbor_order() ahora evalúa ambos extremos de cada contorno
  (inicio y fin), no solo el primero, reduciendo saltos también ENTRE
  contornos.
- NUEVO: costura fija + dos estrategias para evitar el exceso de material
  en el punto donde el contorno cierra sobre sí mismo (inicio == fin):
    * Solución 1 (apply_solution_1_gap_trim): recorta el último segmento
      para no volver a pasar por el punto de partida.
    * Solución 2 (apply_solution_2_sacrificial_tab): agrega un segmento de
      sacrificio pegado a la costura, para imprimir de forma continua sin
      detener la extrusión sobre la pieza.
  Ver sección "Costura fija y recorte de cierre (Solución 1)" y "Segmento
  de sacrificio pegado a la costura (Solución 2)" más abajo.
"""

import numpy as np
import trimesh
from visualizadores import visualize_optimized_route_3d

# -------------------------
# Carga y configuración
# -------------------------
def config(stl, layer_height):
    mesh = trimesh.load(stl)
    z_min = mesh.bounds[0][2]
    z_max = mesh.bounds[1][2]
    layers_z = np.arange(z_min, z_max, layer_height)
    return mesh, layers_z


# -------------------------
# Slicing por capa
# -------------------------
def slice_mesh(mesh, z):
    """
    Corta la malla en el plano Z indicado y devuelve la lista de polígonos
    (Shapely) válidos de esa capa.
    """
    plane_origin = [0, 0, z]
    plane_normal = [0, 0, 1]

    section = mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)

    if section is None:
        return []

    if isinstance(section, trimesh.path.Path3D):
        # Si el corte no queda perfectamente en el plano XY, to_2D() lo proyecta.
        paths_2d_result = section.to_2D()
        polygons = []
        if isinstance(paths_2d_result, tuple):
            for path_2d_item in paths_2d_result:
                if isinstance(path_2d_item, trimesh.path.Path2D):
                    polygons.extend(path_2d_item.polygons_full)
        elif isinstance(paths_2d_result, trimesh.path.Path2D):
            polygons.extend(paths_2d_result.polygons_full)
    elif isinstance(section, trimesh.path.Path2D):
        polygons = list(section.polygons_full)
    else:
        print(f"Warning: Unexpected section type: {type(section)}")
        polygons = []

    # FIX: descartar polígonos inválidos o vacíos. Un polígono con anillo
    # auto-intersectado (is_valid == False) tiene sus coordenadas en un orden
    # que "cruza" el contorno en vez de recorrerlo de forma continua, lo cual
    # se traduce en saltos erráticos al imprimir/generar el toolpath.
    polygons = [p for p in polygons if p is not None and p.is_valid and not p.is_empty]

    return polygons


def get_layer_coordinates(all_layers, layers_z, z_offset=0.0):
    def to_fixed2(value):
        return round(float(value), 2)

    layer_coordinates = []
    for z, polygons in zip(layers_z, all_layers):
        z_with_offset = to_fixed2(z + z_offset)
        layer_coords = []
        for polygon in polygons:
            x, y = polygon.exterior.xy
            coords = [(to_fixed2(xi), to_fixed2(yi), z_with_offset) for xi, yi in zip(x, y)]
            layer_coords.append(coords)
        layer_coordinates.append(layer_coords)
    return layer_coordinates


# -------------------------
# Generación de toolpaths (recorrido crudo, sin optimizar)
# -------------------------
def generate_toolpath(polygons):
    return [np.array(poly.exterior.coords) for poly in polygons]


def generate_all_toolpaths(all_layers):
    return [generate_toolpath(layer_polygons) for layer_polygons in all_layers]


# -------------------------
# Optimización de ruteo (heurística del vecino más cercano)
# -------------------------
def _dist2(p, q):
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2


def _is_closed(contour, tol=1e-6):
    """True si el primer y último punto del contorno coinciden (anillo cerrado)."""
    if len(contour) < 2:
        return False
    p0, p1 = contour[0], contour[-1]
    return abs(p0[0] - p1[0]) <= tol and abs(p0[1] - p1[1]) <= tol


def rotate_contour_to_start(contour, start_point):
    """
    Rota un contorno (lista de puntos) para que empiece en el punto más
    cercano a start_point, sin alterar el orden relativo de los puntos.

    IMPORTANTE: si el contorno es un anillo cerrado (primer punto == último,
    como en un cuadrado o círculo), se quita el punto de cierre duplicado
    antes de rotar y se lo vuelve a agregar al final DESPUÉS de rotar, para
    que el contorno rotado también quede cerrado. Sin esto, la rotación
    "cortaba" el último tramo del contorno (p. ej. un cuadrado quedaba
    abierto por un lado antes de subir a la siguiente capa).
    """
    if not contour or len(contour) < 2:
        return contour

    closed = _is_closed(contour)
    pts = contour[:-1] if closed else list(contour)

    if len(pts) < 2:
        return contour

    closest_idx = min(range(len(pts)), key=lambda i: _dist2(pts[i], start_point))
    rotated = pts[closest_idx:] + pts[:closest_idx]

    if closed:
        rotated.append(rotated[0])  # re-cerrar el anillo en el nuevo punto de partida

    return rotated


def _nearest_neighbor_order(contours, start_point=None):
    """
    Ordena una lista de contornos con la heurística del vecino más cercano
    (Nearest Neighbor heuristic), la aproximación greedy clásica para
    problemas tipo TSP (Travelling Salesman Problem).

    A diferencia de la versión anterior, para cada contorno candidato se
    evalúan AMBOS extremos (inicio y fin) contra el último punto visitado,
    ya que un contorno cerrado puede recorrerse en cualquier dirección.
    El contorno elegido se rota para comenzar en el extremo más cercano.
    """
    if not contours:
        return contours
    if len(contours) == 1:
        contour = contours[0]
        if start_point is not None:
            contour = rotate_contour_to_start(contour, start_point)
        return [contour]

    remaining = list(range(len(contours)))
    ordered = []
    last_point = start_point if start_point is not None else contours[0][0]

    while remaining:
        best_idx = None
        best_dist = float("inf")
        for idx in remaining:
            contour = contours[idx]
            for endpoint in (contour[0], contour[-1]):
                d = _dist2(endpoint, last_point)
                if d < best_dist:
                    best_dist = d
                    best_idx = idx

        contour = rotate_contour_to_start(contours[best_idx], last_point)
        ordered.append(contour)
        last_point = contour[-1]
        remaining.remove(best_idx)

    return ordered


def optimize_layer_path(layer_coords, start_point=None):
    """
    Optimiza el orden de recorrido de los contornos DENTRO de una misma capa.
    """
    return _nearest_neighbor_order(layer_coords, start_point=start_point)


def optimize_all_layers_path(coordinates):
    """
    Optimiza el ruteo completo:
    1. Dentro de cada capa: vecino más cercano entre contornos.
    2. Entre capas: la capa siguiente empieza en el punto más cercano al
       último punto de la capa anterior.
    """
    if not coordinates:
        return coordinates

    optimized = [optimize_layer_path(layer) for layer in coordinates]
    print("✓ Paso 1: Paths dentro de capas optimizados (vecino más cercano entre contornos)")

    for i in range(len(optimized) - 1):
        if not optimized[i] or not optimized[i + 1]:
            continue
        last_point_current = optimized[i][-1][-1]
        optimized[i + 1] = optimize_layer_path(optimized[i + 1], start_point=last_point_current)

    print("✓ Paso 2: Paths entre capas optimizados (punto inicial más cercano al final de la capa anterior)")
    return optimized


# -------------------------
# Segmento de sacrificio (purga que no toca la pieza) — usado ENTRE capas
# -------------------------
def compute_part_bounds_xy(coordinates):
    """
    Calcula el centroide XY y el radio máximo de la pieza a partir de TODOS
    los puntos de todas las capas/contornos ya generados.

    El "radio máximo" es la distancia más grande, en cualquier capa, entre
    el centroide y un punto de la pieza. Se usa como referencia segura: un
    punto ubicado más allá de ese radio (desde el centroide) queda
    garantizado fuera de la silueta de la pieza en CUALQUIER capa, sin
    importar la forma de cada corte transversal.
    """
    all_xy = np.array([
        (p[0], p[1])
        for capa in coordinates
        for contorno in capa
        for p in contorno
    ])
    if len(all_xy) == 0:
        return np.array([0.0, 0.0]), 0.0

    centroid_xy = all_xy.mean(axis=0)
    radii = np.linalg.norm(all_xy - centroid_xy, axis=1)
    max_radius = float(radii.max())
    return centroid_xy, max_radius


def compute_sacrificial_point(primer_punto, centroid_xy, max_radius, margin=15.0):
    """
    Calcula el punto de arranque de la línea de "sacrificio" (purga),
    ubicado deliberadamente FUERA del volumen de la pieza, en la dirección
    que va desde el centroide de la pieza hacia el punto de inicio de la
    capa (primer_punto).

    A diferencia de un segmento de purga aislado, este punto está pensado
    para ser el ORIGEN de una línea que luego SE CONECTA con la figura: se
    extruye en línea recta desde aquí hasta primer_punto, de modo que el
    chorreo/goteo inicial y el cebado del flujo queden sobre esa línea de
    aproximación (que se puede recortar o dejar como "costura" externa) en
    vez de sobre el arranque limpio del contorno real.

    Args:
        primer_punto: (x, y, z) punto real de inicio de la capa; la línea
                      de sacrificio termina exactamente en este punto.
        centroid_xy:  centroide XY de la pieza (ver compute_part_bounds_xy).
        max_radius:   radio máximo de la pieza (ver compute_part_bounds_xy).
        margin:       distancia (mm) más allá del radio máximo a la que se
                      ubica el punto de arranque; también funciona como
                      "largo" de la línea de sacrificio.

    Returns:
        punto_sacrificio (x, y, z), a la misma Z que primer_punto (la
        elevación Z+5 se aplica en el generador de KRL, igual que con los
        demás movimientos de viaje).
    """
    p_xy = np.array([primer_punto[0], primer_punto[1]])
    direction = p_xy - centroid_xy
    norm = np.linalg.norm(direction)

    if norm < 1e-6:
        # Caso degenerado: el punto de inicio coincide con el centroide.
        # Se usa una dirección arbitraria fija en vez de dividir por cero.
        direction = np.array([1.0, 0.0])
    else:
        direction = direction / norm

    safe_dist = max_radius + margin
    start_xy = centroid_xy + direction * safe_dist

    z = primer_punto[2]
    return (round(float(start_xy[0]), 2), round(float(start_xy[1]), 2), z)


# -------------------------------------------------------------------------
# Costura fija y recorte de cierre (SOLUCIÓN 1)
# -------------------------------------------------------------------------
# Problema: cada contorno cerrado viene con contour[0] == contour[-1]
# (Shapely repite el punto de cierre). codigo_contornos() imprime TODOS los
# puntos, incluido ese cierre, por lo que el cabezal vuelve a extruir
# exactamente sobre el punto de partida -> exceso de material en la
# costura. Además, con optimize_all_layers_path() la costura de cada capa
# cambia según el último punto de la capa anterior (vecino más cercano),
# por lo que ni siquiera queda siempre en el mismo lugar.
#
# Esta solución resuelve ambas cosas:
#   1. apply_fixed_seam(): fuerza la MISMA costura (mismo punto de
#      arranque relativo) en todas las capas.
#   2. trim_closing_gap(): recorta el último segmento para que el
#      recorrido NO vuelva a pasar por el punto de partida.
# -------------------------------------------------------------------------
def _first_point_xy(coordinates):
    """
    Devuelve el (x, y) del primer punto del primer contorno no vacío,
    recorriendo capas en orden. Se usa como costura de referencia por
    defecto cuando el usuario no entrega una explícita.
    """
    for capa in coordinates:
        for contorno in capa:
            if contorno:
                p0 = contorno[0]
                return (p0[0], p0[1])
    return None


def apply_fixed_seam(coordinates, seam_reference=None):
    """
    Fija la costura (punto de inicio/cierre) de TODOS los contornos, en
    TODAS las capas, al punto del contorno más cercano a `seam_reference`
    (x, y) — el MISMO punto de referencia para cada capa.

    Esto reemplaza, para efectos de la costura, el criterio de
    optimize_all_layers_path() (que elegía el punto de inicio según el
    último punto de la capa anterior). Con costura fija, la línea de unión
    queda siempre en el mismo lugar relativo de la pieza en todas las
    capas, en vez de ir "girando" capa a capa.

    Si `seam_reference` es None, se usa el primer punto del primer
    contorno de la primera capa (tal como venga `coordinates`) como
    referencia constante para todas las capas siguientes.

    Devuelve `coordinates` con la misma estructura anidada
    (capas -> contornos -> puntos).
    """
    if not coordinates:
        return coordinates

    if seam_reference is None:
        seam_reference = _first_point_xy(coordinates)
        if seam_reference is None:
            return coordinates

    resultado = []
    for capa in coordinates:
        nueva_capa = []
        for contorno in capa:
            if not contorno:
                continue
            nueva_capa.append(rotate_contour_to_start(contorno, seam_reference))
        resultado.append(nueva_capa)
    return resultado


def trim_closing_gap(contour, delta):
    """
    Recorta el segmento de CIERRE de un contorno cerrado (contour[0] ==
    contour[-1]) para que el recorrido no vuelva a pasar exactamente por
    el punto de partida.

    Reglas (distancias medidas en XY; la Z se mantiene igual a la de la
    capa):
      - Si la distancia entre el penúltimo punto real (contour[-2]) y el
        punto de cierre (= punto de partida) es MENOR que `delta`: el
        contorno simplemente termina en ese penúltimo punto (se elimina
        el punto de cierre duplicado, sin agregar uno nuevo).
      - Si es MAYOR o igual: el punto de cierre se reemplaza por uno
        nuevo, ubicado sobre ese mismo último segmento, exactamente a
        `delta` mm del punto de partida. El contorno queda "abierto" a esa
        distancia del arranque en vez de cerrar el anillo completo.

    Para que el hueco quede siempre en el mismo lugar de la pieza (capa a
    capa), llamar primero a apply_fixed_seam() sobre `coordinates` (o usar
    directamente apply_solution_1_gap_trim(), que ya lo hace).

    Si el contorno no es un anillo cerrado, se devuelve sin cambios.
    """
    if not contour or len(contour) < 2:
        return contour
    if not _is_closed(contour):
        return contour

    start_point = contour[0]
    p_prev = contour[-2]
    seg_len = float(np.sqrt(_dist2(p_prev, start_point)))

    abierto = list(contour[:-1])  # quitar el punto de cierre duplicado

    if seg_len < 1e-9 or seg_len <= delta:
        # Segmento final más corto que delta (o casi nulo): terminar en el
        # penúltimo punto tal cual, sin dividir nada.
        return abierto

    t = (seg_len - delta) / seg_len
    nuevo_ultimo = (
        round(p_prev[0] + (start_point[0] - p_prev[0]) * t, 2),
        round(p_prev[1] + (start_point[1] - p_prev[1]) * t, 2),
        start_point[2],
    )
    return abierto + [nuevo_ultimo]


def apply_solution_1_gap_trim(coordinates, delta, seam_reference=None):
    """
    Orquesta la Solución 1 completa:
      1. Fija la costura de todos los contornos (misma capa a capa).
      2. Recorta el cierre de cada contorno con trim_closing_gap(delta).

    Devuelve `coordinates` con la misma estructura anidada
    (capas -> contornos -> puntos), lista para pasar directo a
    codigo_contornos(): cada contorno queda ABIERTO (ya no repite el punto
    de partida al final).
    """
    fijas = apply_fixed_seam(coordinates, seam_reference=seam_reference)
    resultado = []
    for capa in fijas:
        nueva_capa = [trim_closing_gap(contorno, delta) for contorno in capa]
        resultado.append(nueva_capa)
    return resultado


# -------------------------------------------------------------------------
# Segmento de sacrificio pegado a la costura (SOLUCIÓN 2)
# -------------------------------------------------------------------------
# En vez de recortar el cierre, se agrega un pequeño "apéndice" de dos
# líneas, pegado al punto de costura, apuntando hacia afuera de la pieza
# (misma dirección centroide -> punto, igual criterio que
# compute_sacrificial_point). Permite imprimir TODO seguido, extruyendo:
#
#     entrada --(ida)--> P0 --> [... contorno completo, cerrado ...] --> P0 --(vuelta)--> salida
#
# entrada y salida son DOS puntos exteriores distintos (separados
# `tab_separation` mm) para que la línea de ida y la de vuelta no queden
# superpuestas. El exceso de material por el arranque/parada de extrusión
# queda en la punta de este apéndice, fuera de la silueta de la pieza, no
# sobre su superficie.
# -------------------------------------------------------------------------
def _seam_tab_endpoints(seam_point, centroid_xy, tab_length, tab_separation):
    """
    Calcula los dos puntos exteriores (entrada y salida) del segmento de
    sacrificio pegado al punto de costura `seam_point`.

    Dirección: desde el centroide de la pieza hacia el propio punto de
    costura (mismo criterio que compute_sacrificial_point), extendida
    `tab_length` mm más allá del punto de costura.

    Los dos puntos (entrada/salida) se separan lateralmente
    `tab_separation` mm (perpendicular a esa dirección), de modo que la
    línea de ida y la de vuelta queden como una "V" angosta en vez de una
    sola línea recorrida dos veces.
    """
    seam_xy = np.array([seam_point[0], seam_point[1]], dtype=float)
    centroid_xy = np.asarray(centroid_xy, dtype=float)

    direction = seam_xy - centroid_xy
    norm = np.linalg.norm(direction)
    direction = direction / norm if norm > 1e-6 else np.array([1.0, 0.0])

    punta = seam_xy + direction * tab_length
    perp = np.array([-direction[1], direction[0]])

    entrada_xy = punta + perp * (tab_separation / 2.0)
    salida_xy = punta - perp * (tab_separation / 2.0)

    z = seam_point[2]
    entrada = (round(float(entrada_xy[0]), 2), round(float(entrada_xy[1]), 2), z)
    salida = (round(float(salida_xy[0]), 2), round(float(salida_xy[1]), 2), z)
    return entrada, salida


def add_seam_sacrificial_tab(contour, centroid_xy, tab_length=10.0, tab_separation=2.0):
    """
    Dado un contorno CERRADO (contour[0] == contour[-1]), calcula un punto
    de entrada y uno de salida por fuera de la pieza, ambos pegados al
    punto de costura (contour[0]).

    No modifica el contorno: devuelve (entrada, contorno, salida). El
    llamador arma la lista final [entrada, *contorno, salida].

    Lanza ValueError si el contorno no es un anillo cerrado (no tendría
    sentido "coser" un apéndice de cierre a un contorno que no cierra).
    """
    if not contour or len(contour) < 2:
        return None, contour, None
    if not _is_closed(contour):
        raise ValueError(
            "add_seam_sacrificial_tab requiere un contorno cerrado "
            "(contour[0] == contour[-1])."
        )

    entrada, salida = _seam_tab_endpoints(contour[0], centroid_xy, tab_length, tab_separation)
    return entrada, contour, salida


def apply_solution_2_sacrificial_tab(coordinates, tab_length=10.0, tab_separation=2.0, seam_reference=None):
    """
    Orquesta la Solución 2 completa:
      1. Fija la costura de todos los contornos (misma capa a capa), igual
         que en la Solución 1 — así el apéndice queda siempre en el mismo
         lugar relativo de la pieza.
      2. Agrega el segmento de sacrificio (entrada/salida) a cada
         contorno, pegado a su punto de costura.

    Devuelve `coordinates` con la misma estructura anidada
    (capas -> contornos -> puntos); cada contorno queda como
    [entrada, *contorno_original_cerrado, salida], listo para pasar
    directo a codigo_contornos() sin más cambios estructurales.
    """
    if not coordinates:
        return coordinates

    centroid_xy, _ = compute_part_bounds_xy(coordinates)
    fijas = apply_fixed_seam(coordinates, seam_reference=seam_reference)

    resultado = []
    for capa in fijas:
        nueva_capa = []
        for contorno in capa:
            if not contorno:
                continue
            entrada, cuerpo, salida = add_seam_sacrificial_tab(
                contorno, centroid_xy, tab_length=tab_length, tab_separation=tab_separation
            )
            nueva_capa.append([entrada] + list(cuerpo) + [salida])
        resultado.append(nueva_capa)
    return resultado


# -------------------------
# Orquestador
# -------------------------
def coordenadas_stl(stl, layer_height, z_offset=0.0, visualize=True):
    mesh, layers_z = config(stl, layer_height)

    all_layers = [slice_mesh(mesh, z) for z in layers_z]
    print(f"Capas generadas: {len(all_layers)} (z_offset={z_offset})")

    coordinates = get_layer_coordinates(all_layers, layers_z, z_offset=z_offset)
    coordinates = optimize_all_layers_path(coordinates)

    if visualize:
        # Muestra el recorrido YA determinado (orden final), coloreado por
        # orden de visita, para verificar de un vistazo que sigue el contorno
        # de forma continua y que las transiciones (línea roja punteada) son
        # razonables. Se abre automáticamente en el navegador.
        visualize_optimized_route_3d(coordinates)

    return [coordinates, all_layers, layers_z]