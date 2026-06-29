import cv2
import numpy as np
import matplotlib.pyplot as plt

# 1. Configuración de parámetros de la escala (según tu imagen)
TEMP_MIN = 21.2
TEMP_MAX = 182.4

def obtener_temperatura(pixel_val, min_val, max_val, t_min, t_max):
    """
    Interpola el valor del píxel para obtener la temperatura.
    Usamos el valor de intensidad (V en HSV) o escala de grises.
    """
    # Normalización simple basada en intensidad
    return t_min + (pixel_val / 255.0) * (t_max - t_min)

def on_click(event):
    if event.xdata is not None and event.ydata is not None:
        ix, iy = int(event.xdata), int(event.ydata)
        
        # Obtenemos el valor del píxel en escala de grises para la intensidad térmica
        pixel_gray = gray_img[iy, ix]
        
        # Calculamos temperatura
        temp = obtener_temperatura(pixel_gray, 0, 255, TEMP_MIN, TEMP_MAX)
        
        print(f"Coordenadas: ({ix}, {iy}) | Intensidad: {pixel_gray} | Temp. Estimada: {temp:.2f}°C")
        
        # Dibujar punto y texto en la imagen
        plt.gca().plot(ix, iy, 'ro', markersize=5)
        plt.gca().text(ix + 5, iy - 5, f"{temp:.1f}°C", color='white', fontsize=10, 
                       bbox=dict(facecolor='black', alpha=0.5))
        plt.draw()

def on_key(event):
    if event.key == 'r':
        # Reiniciar los puntos
        ax.clear()
        ax.imshow(img_rgb)
        ax.set_title("Haz clic en cualquier punto para ver la temperatura\nPresiona 'r' para reiniciar los puntos")
        plt.draw()
        print("Puntos reiniciados")

# Cargar la imagen
image_path = "Trabajo de título/Imagenes/140-1.jpeg"  # Cambia esto por el nombre de tu archivo
img = cv2.imread(image_path)
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Configurar visualización interactiva
fig, ax = plt.subplots(figsize=(10, 12))
ax.imshow(img_rgb)
ax.set_title("Haz clic en cualquier punto para ver la temperatura\nPresiona 'r' para reiniciar los puntos")
cid = fig.canvas.mpl_connect('button_press_event', on_click)
kid = fig.canvas.mpl_connect('key_press_event', on_key)

plt.show()