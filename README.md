# CampusConnect

Plataforma web para **organizar el estudio, formar grupos de estudio y solicitar tutorías**.
Prototipo mínimo viable (MVP) de la asignatura TI3043 Ingeniería de Software, Unidad 3.

**Equipo:** Felipe Rojas (Scrum Master) y Oscar Hernández (Product Owner). Sección C2.

## Qué hace el MVP

| Rol | Funcionalidades |
|---|---|
| Estudiante | Registrarse e iniciar sesión · registrar tramos libres y evaluaciones · **generar y reorganizar un plan de estudio** con pausas activas · unirse a un grupo compatible o crear uno · solicitar y cancelar tutorías |
| Tutor | Publicar disponibilidad · aceptar o rechazar solicitudes (el rechazo exige motivo) |
| Administrador | Gestionar asignaturas y tutores · ver indicadores de uso y exportar CSV |

El **algoritmo planificador** (`campusconnect/planner.py`) prioriza las evaluaciones según peso, dificultad
y cercanía, ubica sesiones solo en los tramos libres y antes de la fecha de cada evaluación, inserta una
pausa activa tras 50 minutos de estudio continuo y avisa cuando las horas no alcanzan (sobrecarga).
El **emparejamiento** (`campusconnect/matching.py`) usa el patrón Strategy.

## Tecnologías

Python 3.10 o superior · Flask · SQLite · HTML y CSS (sin JavaScript) · `unittest` para las pruebas.

## Cómo ejecutarlo (Windows)

```bat
git clone https://github.com/theoscar019/CampusConnect.git
cd CampusConnect
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py --demo
python run.py
```

`python run.py --demo` crea la base de datos con cuentas de prueba y **muestra sus contraseñas una sola vez**
(se generan al azar; no hay contraseñas guardadas en el código). Luego abra http://127.0.0.1:5000.

En Linux o macOS, use `source .venv/bin/activate` en lugar de `.venv\Scripts\activate`.

Variables opcionales (ver `.env.example`): `CAMPUSCONNECT_SECRET_KEY`, `CAMPUSCONNECT_DB`, `CAMPUSCONNECT_HTTPS`.
Si no define la clave secreta, se genera una al azar en cada inicio (las sesiones se cierran al reiniciar).

## Pruebas

```bat
python -m unittest discover -s tests -t . -v
python scripts\benchmark.py 200
```

Los resultados de la última ejecución están en `docs/resultados_pruebas.txt`.

| Archivo | Tipo | Qué verifica |
|---|---|---|
| `tests/test_planner.py` | Unitarias | Prioridad, bloques libres, pausas, sobrecarga, fechas |
| `tests/test_validadores_y_matching.py` | Unitarias | Validación de entradas, política de contraseñas, emparejamiento |
| `tests/test_integracion.py` | Integración | Flujos completos de estudiante, grupos, tutorías y administrador |
| `tests/test_seguridad.py` | Seguridad | Control de acceso, CSRF, inyección SQL, XSS, sesión, bloqueo, cabeceras |

## Medidas de seguridad (OWASP Top 10 2021)

| Categoría | Medida en el código |
|---|---|
| A01 Control de acceso | Decoradores `login_requerido` y `rol_requerido`; cada consulta de borrado o modificación filtra por el dueño del recurso |
| A02 Fallas criptográficas | Contraseñas con hash y sal (scrypt); cookies `HttpOnly` y `SameSite`; opción `Secure` con HTTPS |
| A03 Inyección | Todas las consultas SQL usan parámetros; validación de cada entrada; plantillas con escape automático (XSS); neutralización de fórmulas en el CSV |
| A04 Diseño inseguro | Token CSRF en todos los formularios; límite de tamaño de las peticiones |
| A05 Configuración insegura | Cabeceras CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy; modo debug apagado; errores sin detalle técnico |
| A07 Fallas de autenticación | Política de contraseñas; bloqueo temporal tras 5 intentos; mensaje de error genérico; sesión que expira a los 30 minutos y se renueva al iniciar sesión |
| A09 Registro y monitoreo | Tabla `auditoria` con inicios de sesión, bloqueos, accesos denegados y acciones de administrador |

## Estructura

```
campusconnect/
  __init__.py      fábrica de la aplicación y manejo de errores
  planner.py       algoritmo planificador
  matching.py      emparejamiento de grupos (Strategy)
  validators.py    validación de entradas
  security.py      CSRF, cabeceras, roles, auditoría
  db.py, schema.sql, seed.py
  routes/          auth, estudiante, tutor, admin
  templates/, static/
tests/             pruebas automatizadas
scripts/benchmark.py
docs/resultados_pruebas.txt
```

## Limitaciones del MVP

- Servidor de desarrollo de Flask y base SQLite: para publicar se necesitaría un servidor WSGI, HTTPS y una base de datos de producción.
- El plan cubre los próximos 7 días y no sincroniza con calendarios externos.
- No hay recuperación de contraseña por correo ni autenticación de dos factores.
- Los tiempos de `scripts/benchmark.py` no incluyen latencia de red.
