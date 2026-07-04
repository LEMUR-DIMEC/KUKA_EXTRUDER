"""
Análisis de ensayo de tracción (PLA)
=====================================
Lee el archivo Excel exportado por la máquina de ensayos (hojas "Resultados"
y "Probeta 1"..."Probeta N") y entrega:

  1) Parámetros generales del ensayo (velocidad de ensayo, intervalo de
     memorización-tiempo, etc.)
  2) Un resumen por probeta: fuerza máxima, área, esfuerzo máximo,
     deformación al esfuerzo máximo, fuerza de rotura y esfuerzo a la rotura.
  3) Un gráfico esfuerzo-deformación con la curva de cada probeta.
  4) Un gráfico con la curva promedio (± desviación estándar) de las
     probetas que el usuario elija.

Requisitos:
    pip install pandas matplotlib openpyxl xlrd

Nota: xlrd >= 2.0 solo lee archivos .xls antiguos (no .xlsx), que es
justamente el formato que exporta esta máquina de ensayos.

Uso:
    python analisis_ensayo_traccion.py
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# CONFIGURACIÓN — editar según necesidad
# ----------------------------------------------------------------------

ARCHIVO_EXCEL = "Análisis probetas/ensayo de traccion PLA.xls"

# Probetas a incluir en la curva promedio. Comentar/quitar números para
# excluir una probeta del promedio (por ejemplo si es un outlier).
PROBETAS_PARA_PROMEDIO = [1, 2, 3, 4, 5, 6, 7]

CARPETA_SALIDA = "Análisis probetas"  # dónde guardar los gráficos y el resumen en CSV


# ----------------------------------------------------------------------
# 1) Parámetros generales y resumen por probeta (hoja "Resultados")
# ----------------------------------------------------------------------

def cargar_resultados(path):
    """Lee la hoja 'Resultados' y separa parámetros generales del ensayo
    del resumen numérico por probeta."""
    df = pd.read_excel(path, sheet_name="Resultados", header=0)
    df = df.rename(columns={"Unnamed: 0": "Probeta"})
    df = df.drop(index=0).reset_index(drop=True)  # la fila 0 son las unidades

    df["N_probeta"] = df["Probeta"].str.extract(r"(\d+)").astype(int)

    for col in ["Velocidad de ensayo", "Intervalo memorización-tiempo",
                "Fmax", "S0", "Deformación nominal en Fmax", "FRotura"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    parametros_generales = {
        "Velocidad de ensayo (mm/min)": df["Velocidad de ensayo"].iloc[0],
        "Intervalo memorización-tiempo (s)": df["Intervalo memorización-tiempo"].iloc[0],
    }

    resumen = pd.DataFrame({
        "Probeta": df["Probeta"],
        "Fuerza máxima (N)": df["Fmax"],
        "Área (mm²)": df["S0"],
        "Esfuerzo máximo (MPa)": df["Fmax"] / df["S0"],
        "Deformación al esfuerzo máximo (%)": df["Deformación nominal en Fmax"],
        "Fuerza rotura (N)": df["FRotura"],
        "Esfuerzo a la rotura (MPa)": df["FRotura"] / df["S0"],
    })

    return parametros_generales, resumen, df.set_index("N_probeta")["S0"]


# ----------------------------------------------------------------------
# 2) Curvas esfuerzo-deformación individuales (hojas "Probeta N")
# ----------------------------------------------------------------------

def cargar_curva_probeta(path, numero, area_mm2):
    """Lee la curva deformación(%)-fuerza(N) de una probeta y devuelve
    deformación (%) y esfuerzo (MPa)."""
    hoja = f"Probeta {numero}"
    df = pd.read_excel(path, sheet_name=hoja, header=None, skiprows=3)
    df.columns = ["deformacion_%", "fuerza_N"]
    df = df.dropna().sort_values("deformacion_%")
    deformacion = df["deformacion_%"].to_numpy()
    esfuerzo = df["fuerza_N"].to_numpy() / area_mm2
    return deformacion, esfuerzo


# ----------------------------------------------------------------------
# 3) Gráficos
# ----------------------------------------------------------------------

def graficar_curvas_individuales(curvas, carpeta_salida):
    plt.figure(figsize=(8, 6))
    for numero, (deformacion, esfuerzo) in curvas.items():
        plt.plot(deformacion, esfuerzo, label=f"Probeta {numero}")
    plt.xlabel("Deformación (%)")
    plt.ylabel("Esfuerzo (MPa)")
    plt.title("Curvas esfuerzo-deformación por probeta")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    ruta = f"{carpeta_salida}/curvas_individuales.png"
    plt.savefig(ruta, dpi=150)
    plt.show()
    print(f"Gráfico guardado en: {ruta}")


def graficar_curva_promedio(curvas, probetas_seleccionadas, carpeta_salida):
    """Interpola cada curva seleccionada sobre una grilla común de
    deformación y calcula el promedio ± desviación estándar."""
    seleccionadas = {n: c for n, c in curvas.items() if n in probetas_seleccionadas}
    if not seleccionadas:
        print("No hay probetas seleccionadas para el promedio.")
        return

    # Grilla común: hasta la menor deformación máxima entre las curvas
    # seleccionadas, para no extrapolar más allá de donde rompió alguna probeta.
    deformacion_max_comun = min(defo.max() for defo, _ in seleccionadas.values())
    grilla = np.linspace(0, deformacion_max_comun, 500)

    esfuerzos_interpolados = []
    for numero, (deformacion, esfuerzo) in seleccionadas.items():
        esfuerzos_interpolados.append(np.interp(grilla, deformacion, esfuerzo))
    esfuerzos_interpolados = np.array(esfuerzos_interpolados)

    promedio = esfuerzos_interpolados.mean(axis=0)
    desviacion = esfuerzos_interpolados.std(axis=0)

    plt.figure(figsize=(8, 6))
    
    plt.plot(grilla, promedio, color="black", linewidth=2, label="Promedio")

    plt.xlabel("Deformación (%)")
    plt.ylabel("Esfuerzo (MPa)")
    probetas_txt = ", ".join(str(n) for n in sorted(seleccionadas))
    plt.title(f"Curva promedio (probetas: {probetas_txt})")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    ruta = f"{carpeta_salida}/curva_promedio.png"
    plt.savefig(ruta, dpi=150)
    plt.show()
    print(f"Gráfico guardado en: {ruta}")


# ----------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------

def main():
    parametros_generales, resumen, areas = cargar_resultados(ARCHIVO_EXCEL)

    print("\n=== Parámetros generales del ensayo ===")
    for clave, valor in parametros_generales.items():
        print(f"  {clave}: {valor}")

    print("\n=== Resumen por probeta ===")
    print(resumen.to_string(index=False))

    ruta_csv = f"{CARPETA_SALIDA}/resumen_probetas.csv"
    resumen.to_csv(ruta_csv, index=False)
    print(f"\nResumen guardado en: {ruta_csv}")

    curvas = {}
    for numero in areas.index:
        curvas[numero] = cargar_curva_probeta(ARCHIVO_EXCEL, numero, areas[numero])

    graficar_curvas_individuales(curvas, CARPETA_SALIDA)
    graficar_curva_promedio(curvas, PROBETAS_PARA_PROMEDIO, CARPETA_SALIDA)


if __name__ == "__main__":
    main()
