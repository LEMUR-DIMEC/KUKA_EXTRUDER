def probeta_path(x,y,z,step_y,step_z, offset_z): #tipo cama

    xi,yi= x/2,y/2
    n_point = int(y/step_y)*2 + 2
    n_list= range(n_point)
    n_step = int(z/step_z)
    n_slist = range(n_step)
    layers = []
    
    for layer in n_slist:
        z_level = layer * step_z
        layer_points = []
        for i in n_list:
            if i == 0:
                a,b = xi,yi
            elif i%4 == 1:
                a,b = -x/2, b
            elif i%4 == 2: 
                a,b = a, round(b - step_y, 2)
            elif i%4 == 3: 
                a,b = x/2, b
            elif i%4 == 0 and i != 0: 
                a,b = a, round(b - step_y, 2)
            layer_points.append((a, b, z_level+ offset_z))
        layers.append(layer_points)
    return layers
    

def cuadrado (x,y,offset_z): #para medir ancho de línea
    xi,yi= x/2,y/2
    points = [[(xi,yi,offset_z), (-xi,yi,offset_z), (-xi,-yi,offset_z), (xi,-yi,offset_z), (xi,yi,offset_z)]]

    return points


def probeta_path_z_vertical(x, y, z, step_z, offset_z ):  # Líneas verticales paralelas al eje Z, Y constante

    xi = x / 2
    yi = y 
    zi = offset_z
    n_point = int(z/step_z)*2 + 2
    n_list= range(n_point)
    n_step = int(z/step_z)
    n_slist = range(n_step)
    
    layer_points = []
    for i in n_list:
            if i == 0:
                a,b,c = xi,yi, zi
            elif i%4 == 1:
                a,b,c= -x/2, b, c
            elif i%4 == 2: 
                a,b,c = a, b, round(c + step_z, 2)
            elif i%4 == 3: 
                a,b,c = x/2, b, c   
            elif i%4 == 0 and i != 0: 
                a,b,c= a, b, round(c + step_z, 2)
            layer_points.append((a, b, c))     
    return [layer_points]
  

#print(probeta_path_z_vertical(100, 50, 10, 10, 2))  
# import matplotlib.pyplot as plt
# from mpl_toolkits.mplot3d import Axes3D

#layers = probeta_path(50, 30, 10, 10, 5) # Example parameters: x=50, y=30, z=10, step_x=10, step_z=5
#print(layers)

# # Flatten points for plotting
# points = [point for layer in layers for point in layer]

# fig = plt.figure()
# ax = fig.add_subplot(111, projection='3d')

# x_vals = [p[0] for p in points]
# y_vals = [p[1] for p in points]
# z_vals = [p[2] for p in points]

# ax.scatter(x_vals, y_vals, z_vals)

# for i, (x, y, z) in enumerate(points):
#     ax.text(x, y, z, str(i), fontsize=8)

# ax.set_xlabel('X')
# ax.set_ylabel('Y')
# ax.set_zlabel('Z')
# plt.show() 


