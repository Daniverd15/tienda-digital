/**
 * Formateo de fechas en hora colombiana (America/Bogota = UTC-5).
 *
 * El backend devuelve datetimes sin zona horaria (formato ISO "naive"). Esos
 * timestamps son UTC porque los contenedores Docker corren en UTC. Como el
 * navegador interpreta strings sin TZ como hora LOCAL del usuario, las horas
 * en pantalla quedan corridas. Aquí las parseamos como UTC y formateamos en
 * la zona de Colombia.
 */
const LOCALE = 'es-CO';
const TZ = 'America/Bogota';

/** Convierte un string ISO "naive" del backend a Date asumiendo UTC. */
function parseBackend(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  let s = String(value);
  // Si ya viene con TZ explícita, respetar
  if (/[zZ]$/.test(s) || /[+-]\d\d:?\d\d$/.test(s)) return new Date(s);
  // Si solo es una fecha (yyyy-mm-dd), interpretar como medianoche local
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(`${s}T00:00:00-05:00`);
  // Caso típico: "2026-05-20T15:30:00" sin TZ → asumir UTC
  return new Date(s + 'Z');
}

/** Fecha + hora (ej. "20 may 2026, 10:30 a.m."). */
export function fmtDateTime(value) {
  const d = parseBackend(value);
  if (!d || isNaN(d.getTime())) return '—';
  return d.toLocaleString(LOCALE, {
    timeZone: TZ, dateStyle: 'medium', timeStyle: 'short',
  });
}

/** Solo fecha (ej. "20 may 2026"). */
export function fmtDate(value) {
  const d = parseBackend(value);
  if (!d || isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(LOCALE, { timeZone: TZ, dateStyle: 'medium' });
}

/** Solo hora (ej. "10:30 a.m."). */
export function fmtTime(value) {
  const d = parseBackend(value);
  if (!d || isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString(LOCALE, { timeZone: TZ, timeStyle: 'short' });
}

/** Tiempo relativo simple ("hace 2 horas", "ayer", "el 18 may"). */
export function fmtRelative(value) {
  const d = parseBackend(value);
  if (!d || isNaN(d.getTime())) return '—';
  const diffMs = Date.now() - d.getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return 'hace un momento';
  if (min < 60) return `hace ${min} min`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `hace ${hr} h`;
  const days = Math.floor(hr / 24);
  if (days === 1) return 'ayer';
  if (days < 7) return `hace ${days} días`;
  return fmtDate(value);
}
