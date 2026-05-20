/**
 * Pagina para dejar reseña de un producto entregado (/resenas/:orderId/:productId).
 *
 * Valida en backend que:
 *  - El usuario tenga el pedido ENTREGADO con ese producto.
 *  - No haya reseñado ya esa combinacion (user, product, order).
 *
 * La reseña entra como pendiente (approved=false). El admin la modera
 * antes de que se publique al publico y se actualice el rating del producto.
 */
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Star, Send } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../context/ToastContext';

function StarPicker({ value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '0.35rem', marginTop: 6 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          aria-label={`${n} estrellas`}
          onClick={() => onChange(n)}
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 4 }}
        >
          <Star
            size={32}
            fill={n <= value ? '#ca8a04' : 'none'}
            color={n <= value ? '#ca8a04' : '#cbd0c8'}
            strokeWidth={1.5}
          />
        </button>
      ))}
    </div>
  );
}

export default function CreateReview() {
  const { orderId, productId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (!comment.trim()) {
      toast('Escribe un comentario para enviar tu reseña.', 'warning');
      return;
    }
    setLoading(true);
    try {
      await api.post('/reviews', {
        order_id: Number(orderId),
        product_id: Number(productId),
        rating: Number(rating),
        comment: comment.trim(),
      });
      toast('Reseña publicada. ¡Gracias por tu opinión!', 'success');
      navigate(`/pedidos/${orderId}`);
    } catch (err) {
      toast(err.response?.data?.detail || 'No fue posible registrar la reseña.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page-shell" style={{ maxWidth: 600, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
        <Link to={`/pedidos/${orderId}`} style={{ color: 'var(--neutral-500)', fontSize: '0.875rem', textDecoration: 'none' }}>
          ← Volver al pedido
        </Link>
      </div>

      <div className="section-heading">
        <div>
          <span className="eyebrow">Compra entregada</span>
          <h1>Comparte tu opinión</h1>
        </div>
      </div>

      <form onSubmit={submit} className="section-card" style={{ padding: '1.5rem' }}>
        <p style={{ color: 'var(--neutral-600)', marginBottom: '1.25rem' }}>
          Cuéntale a otros clientes qué te pareció el producto. Tu reseña es visible solo para
          productos que recibiste — por eso aparece con el sello de compra verificada.
        </p>

        <label style={{ display: 'block', fontWeight: 700, fontSize: '0.875rem' }}>
          ¿Cómo lo calificarías?
        </label>
        <StarPicker value={rating} onChange={setRating} />
        <div style={{ fontSize: '0.875rem', color: 'var(--neutral-500)', marginTop: 6 }}>
          {rating === 5 && '¡Excelente!'}
          {rating === 4 && 'Muy bueno'}
          {rating === 3 && 'Aceptable'}
          {rating === 2 && 'Regular'}
          {rating === 1 && 'Malo'}
        </div>

        <label style={{ display: 'block', marginTop: '1.25rem', fontWeight: 700, fontSize: '0.875rem' }}>
          Tu comentario
        </label>
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="¿Qué te gustó? ¿Cómo te quedó la talla? ¿Recomendarías el producto?"
          rows={5}
          style={{
            width: '100%',
            marginTop: 6,
            padding: '0.75rem',
            border: '1px solid var(--neutral-200)',
            borderRadius: 'var(--radius-md)',
            fontFamily: 'inherit',
            fontSize: '0.9375rem',
            resize: 'vertical',
          }}
        />
        <div style={{ fontSize: '0.75rem', color: 'var(--neutral-400)', marginTop: 4, textAlign: 'right' }}>
          {comment.length} / 600
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.5rem' }}>
          <Link to={`/pedidos/${orderId}`} className="btn btn-secondary" style={{ flex: 1 }}>
            Cancelar
          </Link>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ flex: 2, gap: 6 }}
            disabled={loading || !comment.trim()}
          >
            <Send size={15} />
            {loading ? 'Publicando…' : 'Publicar reseña'}
          </button>
        </div>
      </form>
    </main>
  );
}
