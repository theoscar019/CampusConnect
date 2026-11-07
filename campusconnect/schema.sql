PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('estudiante', 'tutor', 'admin')),
    carrera TEXT NOT NULL DEFAULT '',
    activo INTEGER NOT NULL DEFAULT 1,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta TEXT,
    creado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asignaturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    carrera TEXT NOT NULL,
    activa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS evaluaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignaturas(id),
    fecha TEXT NOT NULL,
    ponderacion INTEGER NOT NULL CHECK (ponderacion BETWEEN 1 AND 100),
    dificultad INTEGER NOT NULL CHECK (dificultad BETWEEN 1 AND 5),
    tipo TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bloques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    dia INTEGER NOT NULL CHECK (dia BETWEEN 0 AND 6),
    inicio INTEGER NOT NULL,
    fin INTEGER NOT NULL,
    CHECK (inicio < fin)
);

CREATE TABLE IF NOT EXISTS planes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    creado TEXT NOT NULL,
    alerta TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sesiones_estudio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES planes(id) ON DELETE CASCADE,
    fecha TEXT NOT NULL,
    inicio INTEGER NOT NULL,
    fin INTEGER NOT NULL,
    asignatura TEXT NOT NULL DEFAULT '',
    es_pausa INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS grupos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    asignatura_id INTEGER NOT NULL REFERENCES asignaturas(id),
    capacidad INTEGER NOT NULL DEFAULT 5,
    estado TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'cerrado'))
);

CREATE TABLE IF NOT EXISTS grupo_miembros (
    grupo_id INTEGER NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    PRIMARY KEY (grupo_id, usuario_id)
);

CREATE TABLE IF NOT EXISTS tutor_asignaturas (
    tutor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignaturas(id),
    PRIMARY KEY (tutor_id, asignatura_id)
);

CREATE TABLE IF NOT EXISTS disponibilidad_tutor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tutor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    dia INTEGER NOT NULL CHECK (dia BETWEEN 0 AND 6),
    inicio INTEGER NOT NULL,
    fin INTEGER NOT NULL,
    CHECK (inicio < fin)
);

CREATE TABLE IF NOT EXISTS solicitudes_tutoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tutor_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignaturas(id),
    disponibilidad_id INTEGER NOT NULL REFERENCES disponibilidad_tutor(id) ON DELETE CASCADE,
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'aceptada', 'rechazada', 'cancelada')),
    motivo TEXT NOT NULL DEFAULT '',
    creada TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    mensaje TEXT NOT NULL,
    leida INTEGER NOT NULL DEFAULT 0,
    creada TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    evento TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_usuario ON evaluaciones(usuario_id);
CREATE INDEX IF NOT EXISTS idx_bloques_usuario ON bloques(usuario_id);
CREATE INDEX IF NOT EXISTS idx_solic_tutor ON solicitudes_tutoria(tutor_id, estado);
