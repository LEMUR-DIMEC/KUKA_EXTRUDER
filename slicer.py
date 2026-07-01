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
