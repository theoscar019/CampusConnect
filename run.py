"""Punto de entrada: ``python run.py`` inicia el servidor de desarrollo.

Para cargar datos de demostración: ``python run.py --demo`` (una sola vez).
"""
import sys

from campusconnect import create_app

app = create_app()

if __name__ == "__main__":
    if "--demo" in sys.argv:
        from campusconnect.seed import cargar_datos_demo
        with app.app_context():
            print("Cuentas de demostración (guárdelas, no se vuelven a mostrar):")
            for rol, correo, clave in cargar_datos_demo():
                print(f"  {rol:11s} {correo:30s} {clave}")
    else:
        # debug=False: el modo debug expone una consola remota (OWASP A05).
        app.run(host="127.0.0.1", port=5000, debug=False)
