import numpy as np
import trimesh
import plotly.graph_objects as go
import webbrowser
import os
import matplotlib.pyplot as plt
import json
from visualizadores import visualize_layers_3d
from visualizadores import visualize_toolpaths_3d
from visualizadores import visualize_path_3d    

# Cargar STL y configuración inicial
def config(stl, layer_height):
    mesh = trimesh.load(stl)
    z_min = mesh.bounds[0][2]
    z_max = mesh.bounds[1][2]
    layers_z = np.arange(z_min, z_max, layer_height)
    return mesh, layers_z

# Función de slicing
def slice_mesh(mesh, z):
    # Plano horizontal
    plane_origin = [0, 0, z]
    plane_normal = [0, 0, 1]

    # Intersección malla-plano
    section = mesh.section(plane_origin=plane_origin,
                           plane_normal=plane_normal)

    if section is None:
        return []

    # trimesh.section can return Path2D or Path3D. We need Path2D to get polygons.
    if isinstance(section, trimesh.path.Path3D):
        # If it's a Path3D, convert it to Path2D by projecting it onto the plane.
        # The to_2D method on Path3D usually projects to the XY plane by default.
        paths_2d_result = section.to_2D()
        all_polygons_from_3d = []
        if isinstance(paths_2d_result, tuple):
            for path_2d_item in paths_2d_result:
                if isinstance(path_2d_item, trimesh.path.Path2D):
                    all_polygons_from_3d.extend(path_2d_item.polygons_full)
        elif isinstance(paths_2d_result, trimesh.path.Path2D):
            all_polygons_from_3d.extend(paths_2d_result.polygons_full)
        polygons = all_polygons_from_3d
    elif isinstance(section, trimesh.path.Path2D):
        # If it's already a Path2D, we can directly access its polygons.
        polygons = section.polygons_full
    else:
        # Handle unexpected cases, though usually trimesh.section returns one of the above
        print(f"Warning: Unexpected section type: {type(section)}")
        polygons = []

    return polygons

def get_layer_coordinates(all_layers, layers_z, z_offset=0.0):
    layer_coordinates = []

    def to_fixed2(value):
        # Mantener máxim 2 decimales y evitar int forzado
        return round(float(value), 2)

    for z, polygons in zip(layers_z, all_layers):
        z_with_offset = to_fixed2(z + z_offset)
        layer_coords = []
        for polygon in polygons:
            if polygon is not None:
                x, y = polygon.exterior.xy
                coords = [(to_fixed2(xi), to_fixed2(yi), z_with_offset) for xi, yi in zip(x, y)]
                layer_coords.append(coords)
        layer_coordinates.append(layer_coords)
    return layer_coordinates


# Funciones para generación y visualización de toolpaths
def generate_toolpath(polygons):
    toolpaths = []

    for poly in polygons:
        coords = np.array(poly.exterior.coords)

        # recorrido simple (perímetro)
        toolpaths.append(coords)

    return toolpaths

def generate_all_toolpaths(all_layers):
    """Genera array con las coordenadas de cada capa"""
    all_toolpaths = []
    for layer_polygons in all_layers:
        layer_toolpath = generate_toolpath(layer_polygons)
        all_toolpaths.append(layer_toolpath)
    return all_toolpaths


def coordenadas_stl(stl, layer_height, z_offset=0.0):
    mesh, layers_z = config(stl, layer_height)
    all_layers = []
    for z in layers_z:
        polygons = slice_mesh(mesh, z)
        all_layers.append(polygons)

    print(f"Capas generadas: {len(all_layers)} (z_offset={z_offset})")
    coordinates = get_layer_coordinates(all_layers, layers_z, z_offset=z_offset)

    return [coordinates, all_layers, layers_z]

