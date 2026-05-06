import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../api/client';

export default function CreateReview() {
  const { orderId, productId } = useParams();
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    try {
      await api.post('/reviews', {
        order_id: Number(orderId),
        product_id: Number(productId),
        rating: Number(rating),
        comment
      });
      setMessage('Resena registrada correctamente.');
    } catch (err) {
      setError(err.response?.data?.detail || 'No fue posible registrar la resena.');
    }
  };

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <span className="eyebrow">Compra entregada</span>
        <h1>Crear resena</h1>
        {message && <p className="alert success">{message}</p>}
        {error && <p className="alert error">{error}</p>}
        <label>
          Valoracion
          <select value={rating} onChange={(event) => setRating(event.target.value)}>
            {[5, 4, 3, 2, 1].map((value) => <option value={value} key={value}>{value} estrellas</option>)}
          </select>
        </label>
        <label>
          Comentario
          <textarea value={comment} onChange={(event) => setComment(event.target.value)} required />
        </label>
        <button className="primary-button">Enviar resena</button>
        <Link to={`/pedidos/${orderId}`}>Volver al pedido</Link>
      </form>
    </main>
  );
}

