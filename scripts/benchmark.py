"""Mide tiempos de respuesta y tasa de errores del prototipo.

Uso:  python scripts/benchmark.py [repeticiones]

Las mediciones usan el cliente de pruebas de Flask: incluyen la ejecución completa
de la aplicación y la base de datos, pero NO la latencia de red. Úselas como
referencia relativa y repórtelo así en el informe.
"""
import os
import re
import statistics
import sys
import tempfile
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campusconnect import create_app                      # noqa: E402
from campusconnect.db import ahora, get_db                 # noqa: E402
from campusconnect.planner import Bloque, Evaluacion, generar_plan  # noqa: E402
from campusconnect.security import hash_contrasena          # noqa: E402

CLAVE = "ClaveSegura123"
HOY = date(2026, 11, 9)


def percentil(datos, p):
    datos = sorted(datos)
    return datos[min(len(datos) - 1, int(round(p / 100 * (len(datos) - 1))))]


def medir(nombre, funcion, n):
    tiempos, errores = [], 0
    for _ in range(n):
        t0 = time.perf_counter()
        ok = funcion()
        tiempos.append((time.perf_counter() - t0) * 1000)
        errores += 0 if ok else 1
    return (nombre, n, statistics.mean(tiempos), percentil(tiempos, 50),
            percentil(tiempos, 95), max(tiempos), 100.0 * errores / n)


def main(n):
    tmp = tempfile.TemporaryDirectory()
    app = create_app({"DATABASE": os.path.join(tmp.name, "bench.db"), "TESTING": True, "HOY": HOY})
    with app.app_context():
        d = get_db()
        d.execute("INSERT INTO asignaturas (codigo, nombre, carrera) VALUES ('TI3043', 'Ingeniería de Software', 'X')")
        d.execute("INSERT INTO usuarios (nombre, correo, hash, rol, carrera, creado) VALUES (?,?,?,?,?,?)",
                  ("Estudiante Bench", "bench@inacapmail.cl", hash_contrasena(CLAVE), "estudiante", "X", ahora()))
        for dia in range(7):
            d.execute("INSERT INTO bloques (usuario_id, dia, inicio, fin) VALUES (1, ?, 960, 1200)", (dia,))
        for k in range(1, 6):
            d.execute("INSERT INTO evaluaciones (usuario_id, asignatura_id, fecha, ponderacion, dificultad, tipo) "
                      "VALUES (1, 1, ?, ?, ?, 'Prueba')", (f"2026-11-{12 + k}", 20 + 10 * k, 1 + k % 5))
        d.commit()

    c = app.test_client()

    def token(url):
        return re.search(r'name="csrf_token" value="([^"]+)"', c.get(url).get_data(as_text=True)).group(1)

    def login():
        r = c.post("/login", data={"correo": "bench@inacapmail.cl", "contrasena": CLAVE,
                                   "csrf_token": token("/login")})
        return r.status_code == 302

    assert login()
    tok = token("/panel")
    evals = [Evaluacion(k, 1, "Ingeniería de Software", date(2026, 11, 12 + k), 20 + 10 * k, 1 + k % 5)
             for k in range(1, 6)]
    bloques = [Bloque(dia, 960, 1200) for dia in range(7)]

    filas = [
        medir("Algoritmo generar_plan (5 evaluaciones, 7 días)", lambda: bool(generar_plan(evals, bloques, HOY).sesiones), n * 10),
        medir("GET /login", lambda: c.get("/login").status_code == 200, n),
        medir("GET /panel", lambda: c.get("/panel").status_code == 200, n),
        medir("POST /plan/generar", lambda: c.post("/plan/generar", data={"csrf_token": tok}).status_code == 302, n),
        medir("GET /plan", lambda: c.get("/plan").status_code == 200, n),
        medir("GET /evaluaciones", lambda: c.get("/evaluaciones").status_code == 200, n),
    ]
    # El login es más lento a propósito: el hash de contraseñas (scrypt) frena ataques de fuerza bruta.
    cl = app.test_client()
    def login_nuevo():
        t = re.search(r'name="csrf_token" value="([^"]+)"', cl.get("/login").get_data(as_text=True)).group(1)
        return cl.post("/login", data={"correo": "bench@inacapmail.cl", "contrasena": CLAVE, "csrf_token": t}).status_code == 302
    filas.append(medir("POST /login (incluye verificación de hash)", login_nuevo, max(20, n // 5)))

    print(f"{'Prueba':54s} {'n':>5s} {'media':>8s} {'p50':>8s} {'p95':>8s} {'máx':>8s} {'errores':>8s}")
    for nombre, cant, media, p50, p95, mx, err in filas:
        print(f"{nombre:54s} {cant:5d} {media:7.2f}ms {p50:7.2f}ms {p95:7.2f}ms {mx:7.2f}ms {err:7.1f}%")
    tmp.cleanup()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
