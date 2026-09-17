"""
slicer.py
---------
"""

import numpy as np
import trimesh
from visualizadores import visualize_optimized_route_3d


# Carga y configuración
def config(stl, layer_height):
    mesh = trimesh.load(stl)
    z_min = mesh.bounds[0][2]
    z_max = mesh.bounds[1][2]
    layers_z = np.arange(z_min, z_max, layer_height)
    return mesh, layers_z



# Slicing por capa
def slice_mesh(mesh, z):

    plane_origin = [0, 0, z]
    plane_normal = [0, 0, 1]

    section = mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)

    if section is None:
        return []

    if isinstance(section, trimesh.path.Path3D):
        
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



# Generación de toolpaths (recorrido crudo, sin optimizar)
def generate_toolpath(polygons):
    return [np.array(poly.exterior.coords) for poly in polygons]


def generate_all_toolpaths(all_layers):
    return [generate_toolpath(layer_polygons) for layer_polygons in all_layers]


# Optimización de ruteo (heurística del vecino más cercano)
def _dist2(p, q):
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2


def _is_closed(contour, tol=1e-6):
    """True si el primer y último punto del contorno coinciden (anillo cerrado)."""
    if len(contour) < 2:
        return False
    p0, p1 = contour[0], contour[-1]
    return abs(p0[0] - p1[0]) <= tol and abs(p0[1] - p1[1]) <= tol


def rotate_contour_to_start(contour, start_point):

    if not contour or len(contour) < 2:
        return contour

    closed = _is_closed(contour)
    pts = contour[:-1] if closed else list(contour)

    if len(pts) < 2:
        return contour

    closest_idx = min(range(len(pts)), key=lambda i: _dist2(pts[i], start_point))
    rotated = pts[closest_idx:] + pts[:closest_idx]

    if closed:
        rotated.append(rotated[0])  

    return rotated


def _nearest_neighbor_order(contours, start_point=None):

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



# Segmento de sacrificio (purga que no toca la pieza) — usado ENTRE capas
def compute_part_bounds_xy(coordinates):

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


def _first_point_xy(coordinates):
    for capa in coordinates:
        for contorno in capa:
            if contorno:
                p0 = contorno[0]
                return (p0[0], p0[1])
    return None


def apply_fixed_seam(coordinates, seam_reference=None):

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
    if not contour or len(contour) < 2:
        return contour
    if not _is_closed(contour):
        return contour

    start_point = contour[0]
    p_prev = contour[-2]
    seg_len = float(np.sqrt(_dist2(p_prev, start_point)))

    abierto = list(contour[:-1])  

    if seg_len < 1e-9 or seg_len <= delta:
        return abierto

    t = (seg_len - delta) / seg_len
    nuevo_ultimo = (
        round(p_prev[0] + (start_point[0] - p_prev[0]) * t, 2),
        round(p_prev[1] + (start_point[1] - p_prev[1]) * t, 2),
        start_point[2],
    )
    return abierto + [nuevo_ultimo]


def apply_solution(coordinates, delta, seam_reference=None):
    fijas = apply_fixed_seam(coordinates, seam_reference=seam_reference)
    resultado = []
    for capa in fijas:
        nueva_capa = [trim_closing_gap(contorno, delta) for contorno in capa]
        resultado.append(nueva_capa)
    return resultado

def coordenadas_stl(stl, layer_height, z_offset=0.0, visualize=True):
    mesh, layers_z = config(stl, layer_height)

    all_layers = [slice_mesh(mesh, z) for z in layers_z]
    print(f"Capas generadas: {len(all_layers)} (z_offset={z_offset})")

    coordinates = get_layer_coordinates(all_layers, layers_z, z_offset=z_offset)
    coordinates = optimize_all_layers_path(coordinates)

    if visualize:

        visualize_optimized_route_3d(coordinates)

    return [coordinates, all_layers, layers_z]
