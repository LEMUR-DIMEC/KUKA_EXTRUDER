import trimesh
import numpy as np

def slice_stl_perimeters(stl_path, slice_height=2.0):
    """
    Load an STL file and extract outer perimeter (x, y) points every `slice_height` mm in Z.

    Returns:
        List of lists of (x, y) tuples per slice layer.
    """
    # Load the mesh (handles both ASCII and binary STL)
    mesh = trimesh.load_mesh(stl_path)

    # Merge Scene to Trimesh if needed
    if hasattr(mesh, 'geometry'):
        mesh = mesh.dump(concatenate=True)

    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError("Expected a single Trimesh object")

    if not mesh.is_watertight:
        print("Warning: mesh is not watertight — slicing may be inaccurate.")

    z_min = mesh.bounds[0][2]
    z_max = mesh.bounds[1][2]

    perimeters_by_layer = []

    for z in np.arange(z_min, z_max, slice_height):
        section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if section is None:
            continue

        # Convert the 3D section into 2D
        path_2D, _ = section.to_2D()

        # Each polygon is already a Shapely geometry
        for poly in path_2D.polygons_full:
            if poly.is_valid and not poly.is_empty:
                # Get outer perimeter as (x, y) list
                perimeter = list(poly.exterior.coords)
                # approximate the perimeter values to 2 decimal places
                perimeter = [(round(x, 2), round(y, 2)) for x, y in perimeter]
                perimeters_by_layer.append(perimeter)

    return perimeters_by_layer

# take positions from slices


def extract_positions_from_slices(slices, slice_height=1.0):
    """
    Extract positions from the slices data.

    Returns:
        List of (x, y, z) tuples for each slice.
    """
    positions = []
    for i, layer in enumerate(slices):
        z = i * slice_height
        for x, y in layer:
            positions.append((x, y, z))
    return positions
