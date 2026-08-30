import trimesh

from shapely.geometry import Polygon





def ensure_closed(points):

    if points[0] != points[-1]:

        return points + [points[0]]

    return points





def convert_points(points, scale):

    converted = []



    for x, y in points:

        converted.append((x * scale, -y * scale))



    return converted





def build_polygon_from_loops(loops, scale):

    outer_loop = None

    hole_loops = []



    for loop in loops:

        if loop["type"] == "outer":

            outer_loop = loop["points"]

        elif loop["type"] == "hole":

            hole_loops.append(loop["points"])



    if outer_loop is None:

        raise ValueError("No outer border defined.")



    outer_points = convert_points(ensure_closed(outer_loop), scale)



    hole_points = [

        convert_points(ensure_closed(hole), scale)

        for hole in hole_loops

    ]



    polygon = Polygon(shell=outer_points, holes=hole_points)



    if not polygon.is_valid:

        raise ValueError(

            "The polygon is invalid. Check crossing lines, bad holes, "

            "or holes outside the border."

        )



    if polygon.area <= 0:

        raise ValueError("The polygon area is zero or negative.")



    return polygon





def create_extruded_mesh(loops, scale, thickness):

    polygon = build_polygon_from_loops(loops, scale)



    mesh = trimesh.creation.extrude_polygon(

        polygon,

        height=thickness

    )



    return mesh





def create_extruded_stl(loops, scale, thickness, output_path):

    mesh = create_extruded_mesh(

        loops=loops,

        scale=scale,

        thickness=thickness

    )



    mesh.export(output_path) 