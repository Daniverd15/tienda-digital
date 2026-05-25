/**
 * Hook generico para cargar datos asincronos en componentes React.
 *
 * Encapsula el patron repetitivo de "useState + useEffect + fetch + setData":
 *
 *   const { data, loading, error, setData } = useAsync(async () => {
 *     const { data } = await api.get('/products');
 *     return data;
 *   }, []);
 *
 * @param factory  funcion async que devuelve los datos a cargar.
 * @param deps     array de dependencias (igual que useEffect). Default [].
 * @returns        { data, loading, error, setData }
 *
 * Caracteristicas:
 *   - Maneja el flag `active` para evitar setState despues de unmount
 *     (causa warning de React). Si el componente se desmonta antes de que
 *     la request termine, ignoramos el resultado.
 *   - Extrae automaticamente el `detail` del response de FastAPI para
 *     mensajes de error legibles. Si no hay detail, usa un mensaje generico.
 *   - Expone `setData` para que el caller pueda actualizar el state desde
 *     fuera (ej. tras un POST exitoso, sin tener que refrescar todo).
 */
import { useEffect, useState } from 'react';

export function useAsync(factory, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    // Flag para ignorar el resultado si el componente se desmonto antes de
    // que la promise resuelva (evita setState en componente unmounted).
    let active = true;
    setLoading(true);
    setError('');
    factory()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        // Extraemos el detail del response de FastAPI si esta disponible.
        // Sino, mostramos un mensaje generico legible al usuario.
        if (active) setError(err.response?.data?.detail || 'No fue posible cargar la informacion.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    // Cleanup function: se ejecuta cuando deps cambian o el componente se desmonta.
    return () => {
      active = false;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, setData };
}
