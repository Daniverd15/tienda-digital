export default function Placeholder({ title = 'Modulo en construccion', subtitle = 'Este modulo se completa en el siguiente incremento.' }) {
  return (
    <section className="page-shell">
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </section>
  );
}

