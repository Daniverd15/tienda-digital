import { CheckCircle, Info, XCircle, AlertTriangle, X } from 'lucide-react';
import { createContext, useCallback, useContext, useState } from 'react';

const ToastCtx = createContext(null);

const ICONS = {
  success: <CheckCircle size={18} />,
  error:   <XCircle size={18} />,
  warning: <AlertTriangle size={18} />,
  info:    <Info size={18} />,
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((message, type = 'success', title = '', duration = 3800) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev.slice(-4), { id, message, type, title }]);
    setTimeout(() => dismiss(id), duration);
    return id;
  }, [dismiss]);

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className="toast-container" aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`} role="alert">
            <span className="toast-icon">{ICONS[t.type]}</span>
            <div className="toast-body">
              {t.title && <div className="toast-title">{t.title}</div>}
              <div className="toast-msg">{t.message}</div>
            </div>
            <button className="toast-close" onClick={() => dismiss(t.id)} aria-label="Cerrar">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => {
  const fn = useContext(ToastCtx);
  if (!fn) throw new Error('useToast must be inside ToastProvider');
  return fn;
};
