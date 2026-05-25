import { useEffect } from 'react';
import { X } from 'lucide-react';

/**
 * Modal — generic dialog overlay.
 * Props: open, onClose, title, children, footer, size ('sm'|'md'|'lg')
 */
export default function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  const widths = { sm: '380px', md: '520px', lg: '720px' };

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="modal-box"
        style={{ '--modal-width': widths[size] }}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <button className="icon-button" onClick={onClose} aria-label="Cerrar modal">
            <X size={18} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
