import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Edit2, ImagePlus, Package, Plus, Tag, Trash2, Warehouse } from 'lucide-react';
import api from '../api/client';
import AdminLayout from '../components/AdminLayout';
import Modal from '../components/Modal';
import Badge from '../components/Badge';
import { useToast } from '../context/ToastContext';

const emptyCategory = { name: '', description: '', active: true, archived: false };
const emptyProduct = {
  category_id: '',
  name: '',
  description: '',
  long_description: '',
  base_price: '',
  published: true,
  archived: false,
  image_url: '',
};
const emptyVariant = { sku: '', color: '', size: '', custom_attribute: '', cost: '', price: '', stock: 0, reserved_stock: 0, active: true };
const emptyMovement = { variant_id: '', movement_type: 'entrada', quantity: 1, reason: '' };

const TABS = [
  { id: 'categories', label: 'Categorías',   icon: <Tag size={15} /> },
  { id: 'products',   label: 'Productos',    icon: <Package size={15} /> },
  { id: 'variants',   label: 'Variantes',    icon: <Package size={15} /> },
  { id: 'inventory',  label: 'Inventario',   icon: <Warehouse size={15} /> },
];

function ImageUploader({ value, onChange, label = 'Imagen del producto' }) {
  const inputRef = useRef();
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await api.post('/admin/upload-image', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      onChange(data.url);
    } catch {
      onChange('');
    } finally { setUploading(false); }
  };

  return (
    <label style={{ display: 'grid', gap: '0.3rem', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-700)', margin: '0.6rem 0' }}>
      {label}
      <div
        className={`img-upload-zone${drag ? ' drag-over' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files[0]); }}
      >
        <input ref={inputRef} type="file" accept="image/*" onChange={(e) => upload(e.target.files[0])} />
        {value ? (
          <>
            <img src={value.startsWith('/uploads/') ? `${import.meta.env.VITE_API_URL}${value}` : value} alt="preview" className="img-upload-preview" />
            <span style={{ fontSize: '0.78rem', color: 'var(--neutral-500)' }}>Haz clic o arrastra para cambiar</span>
          </>
        ) : (
          <div style={{ padding: '0.5rem', color: 'var(--neutral-400)' }}>
            <ImagePlus size={28} style={{ margin: '0 auto 0.5rem' }} />
            <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{uploading ? 'Subiendo…' : 'Haz clic o arrastra una imagen'}</div>
            <div style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>JPG, PNG o WebP</div>
          </div>
        )}
      </div>
    </label>
  );
}

export default function AdminCatalog() {
  const toast = useToast();
  const [tab, setTab] = useState('categories');
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [variants, setVariants] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [categoryForm, setCategoryForm] = useState(emptyCategory);
  const [productForm, setProductForm] = useState(emptyProduct);
  const [variantForm, setVariantForm] = useState(emptyVariant);
  const [movementForm, setMovementForm] = useState(emptyMovement);
  const [editCategory, setEditCategory] = useState(null);
  const [editProduct, setEditProduct] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null); // {type, id, name}
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const [catR, prodR, alertR] = await Promise.all([
      api.get('/admin/categories'),
      api.get('/admin/products'),
      api.get('/admin/inventory/alerts'),
    ]);
    setCategories(catR.data);
    setProducts(prodR.data);
    setAlerts(alertR.data);
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!selectedProduct) return;
    api.get(`/admin/products/${selectedProduct}/variants`).then(({ data }) => setVariants(data));
  }, [selectedProduct]);

  /* ── Categories ── */
  const submitCategory = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (editCategory) {
        await api.put(`/admin/categories/${editCategory.id}`, categoryForm);
        toast('Categoría actualizada.', 'success');
        setEditCategory(null);
      } else {
        await api.post('/admin/categories', categoryForm);
        toast('Categoría creada.', 'success');
      }
      setCategoryForm(emptyCategory);
      load();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al guardar categoría.', 'error');
    } finally { setLoading(false); }
  };

  const archiveCategory = async (id) => {
    await api.patch(`/admin/categories/${id}/archive`).catch(() => api.put(`/admin/categories/${id}`, { archived: true }));
    toast('Categoría archivada.', 'success');
    load();
  };

  const startEditCategory = (cat) => {
    setEditCategory(cat);
    setCategoryForm({ name: cat.name, description: cat.description || '', active: cat.active, archived: cat.archived });
    setTab('categories');
  };

  /* ── Products ── */
  const submitProduct = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = { ...productForm, category_id: Number(productForm.category_id), base_price: Number(productForm.base_price) };
      if (editProduct) {
        await api.put(`/admin/products/${editProduct.id}`, payload);
        toast('Producto actualizado.', 'success');
        setEditProduct(null);
      } else {
        await api.post('/admin/products', payload);
        toast('Producto creado.', 'success');
      }
      setProductForm(emptyProduct);
      load();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al guardar producto.', 'error');
    } finally { setLoading(false); }
  };

  const startEditProduct = (prod) => {
    setEditProduct(prod);
    setProductForm({
      category_id: prod.category_id || '',
      name: prod.name,
      description: prod.description || '',
      long_description: prod.long_description || '',
      base_price: prod.base_price,
      published: prod.published,
      archived: prod.archived,
      image_url: prod.image_url || '',
    });
    setTab('products');
  };

  /* ── Variants ── */
  const submitVariant = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post(`/admin/products/${selectedProduct}/variants`, {
        ...variantForm,
        cost: Number(variantForm.cost),
        price: Number(variantForm.price),
        stock: Number(variantForm.stock),
        reserved_stock: Number(variantForm.reserved_stock),
      });
      toast('Variante creada.', 'success');
      setVariantForm(emptyVariant);
      const { data } = await api.get(`/admin/products/${selectedProduct}/variants`);
      setVariants(data);
      load();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al crear variante.', 'error');
    } finally { setLoading(false); }
  };

  /* ── Inventory movement ── */
  const submitMovement = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/admin/inventory/movements', {
        ...movementForm,
        variant_id: Number(movementForm.variant_id),
        quantity: Number(movementForm.quantity),
      });
      toast('Movimiento registrado.', 'success');
      setMovementForm(emptyMovement);
      load();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al registrar movimiento.', 'error');
    } finally { setLoading(false); }
  };

  /* ── Render helpers ── */
  const allVariants = products.flatMap((p) => (p.variants || []).map((v) => ({ ...v, product_name: p.name })));

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">RF-07</span>
          <h1 className="page-title">Catálogo e inventario</h1>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs-bar">
        {TABS.map((t) => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            {t.icon} {t.label}
            {t.id === 'inventory' && alerts.length > 0 && (
              <span style={{ background: '#ef4444', color: '#fff', borderRadius: 99, fontSize: '0.7rem', padding: '1px 6px', marginLeft: 4 }}>
                {alerts.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Categories ── */}
      {tab === 'categories' && (
        <div className="form-grid">
          <form className="form-panel" onSubmit={submitCategory}>
            <h3>{editCategory ? '✏️ Editar categoría' : '＋ Nueva categoría'}</h3>
            <label>
              Nombre *
              <input value={categoryForm.name} onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })} required />
            </label>
            <label>
              Descripción
              <input value={categoryForm.description} onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })} />
            </label>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
              <label className="check-inline">
                <input type="checkbox" checked={categoryForm.active} onChange={(e) => setCategoryForm({ ...categoryForm, active: e.target.checked })} />
                Activa
              </label>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {editCategory ? 'Actualizar' : 'Crear categoría'}
              </button>
              {editCategory && (
                <button type="button" className="btn btn-secondary" onClick={() => { setEditCategory(null); setCategoryForm(emptyCategory); }}>
                  Cancelar
                </button>
              )}
            </div>
          </form>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Estado</th>
                  <th>Archivado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((cat) => (
                  <tr key={cat.id}>
                    <td><strong>{cat.name}</strong><div style={{ fontSize: '0.78rem', color: '#677067' }}>{cat.description}</div></td>
                    <td><Badge variant={cat.active ? 'success' : 'neutral'}>{cat.active ? 'Activa' : 'Inactiva'}</Badge></td>
                    <td><Badge variant={cat.archived ? 'error' : 'neutral'}>{cat.archived ? 'Archivada' : '—'}</Badge></td>
                    <td>
                      <div className="table-actions" style={{ justifyContent: 'flex-end' }}>
                        <button className="btn btn-ghost btn-sm btn-icon" onClick={() => startEditCategory(cat)} title="Editar"><Edit2 size={14} /></button>
                        <button className="btn btn-danger btn-sm btn-icon" onClick={() => archiveCategory(cat.id)} title="Archivar"><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                {categories.length === 0 && (
                  <tr><td colSpan={4} className="state">Sin categorías creadas</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Products ── */}
      {tab === 'products' && (
        <div className="form-grid">
          <form className="form-panel" onSubmit={submitProduct}>
            <h3>{editProduct ? '✏️ Editar producto' : '＋ Nuevo producto'}</h3>
            <label>
              Categoría *
              <select value={productForm.category_id} onChange={(e) => setProductForm({ ...productForm, category_id: e.target.value })} required>
                <option value="">Selecciona categoría</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>Nombre * <input value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} required /></label>
            <label>Descripción corta * <input value={productForm.description} onChange={(e) => setProductForm({ ...productForm, description: e.target.value })} required /></label>
            <label>Descripción larga <textarea value={productForm.long_description} onChange={(e) => setProductForm({ ...productForm, long_description: e.target.value })} /></label>
            <label>Precio base * <input type="number" min="0" step="0.01" value={productForm.base_price} onChange={(e) => setProductForm({ ...productForm, base_price: e.target.value })} required /></label>
            <ImageUploader value={productForm.image_url} onChange={(url) => setProductForm({ ...productForm, image_url: url })} />
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
              <label className="check-inline">
                <input type="checkbox" checked={productForm.published} onChange={(e) => setProductForm({ ...productForm, published: e.target.checked })} />
                Publicado
              </label>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
              <button type="submit" className="btn btn-primary" disabled={loading}>{editProduct ? 'Actualizar' : 'Crear producto'}</button>
              {editProduct && (
                <button type="button" className="btn btn-secondary" onClick={() => { setEditProduct(null); setProductForm(emptyProduct); }}>Cancelar</button>
              )}
            </div>
          </form>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Categoría</th>
                  <th>Precio</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {products.map((prod) => (
                  <tr key={prod.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        {prod.image_url ? (
                          <img src={prod.image_url} alt={prod.name} style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid #e1e5de' }} />
                        ) : (
                          <div style={{ width: 40, height: 40, borderRadius: 8, background: '#f0f2ee', display: 'grid', placeItems: 'center' }}><Package size={16} color="#9ca4a0" /></div>
                        )}
                        <div>
                          <strong style={{ display: 'block', fontSize: '0.875rem' }}>{prod.name}</strong>
                          <span style={{ fontSize: '0.75rem', color: '#9ca4a0' }}>{prod.stock} en stock</span>
                        </div>
                      </div>
                    </td>
                    <td><span className="category-chip">{prod.category_name}</span></td>
                    <td style={{ fontWeight: 700 }}>${Number(prod.base_price).toLocaleString('es-CO')}</td>
                    <td><Badge variant={prod.published ? 'success' : 'neutral'}>{prod.published ? 'Publicado' : 'Oculto'}</Badge></td>
                    <td>
                      <div className="table-actions" style={{ justifyContent: 'flex-end' }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => { startEditProduct(prod); }}>
                          <Edit2 size={13} /> Editar
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => { setSelectedProduct(prod.id); setTab('variants'); }}>
                          Variantes
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {products.length === 0 && (
                  <tr><td colSpan={5} className="state">Sin productos creados</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Variants ── */}
      {tab === 'variants' && (
        <div className="form-grid">
          <form className="form-panel" onSubmit={submitVariant}>
            <h3>＋ Nueva variante</h3>
            <label>
              Producto *
              <select value={selectedProduct} onChange={(e) => setSelectedProduct(e.target.value)} required>
                <option value="">Selecciona producto</option>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label>
              SKU
              <input value={variantForm.sku} placeholder="Se genera automáticamente si se deja vacío" onChange={(e) => setVariantForm({ ...variantForm, sku: e.target.value })} />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <label>Color <input value={variantForm.color} onChange={(e) => setVariantForm({ ...variantForm, color: e.target.value })} /></label>
              <label>Talla <input value={variantForm.size} onChange={(e) => setVariantForm({ ...variantForm, size: e.target.value })} /></label>
            </div>
            <label>Atributo personalizado <input value={variantForm.custom_attribute} onChange={(e) => setVariantForm({ ...variantForm, custom_attribute: e.target.value })} /></label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
              <label>Costo * <input type="number" min="0" step="0.01" value={variantForm.cost} onChange={(e) => setVariantForm({ ...variantForm, cost: e.target.value })} required /></label>
              <label>Precio venta * <input type="number" min="0" step="0.01" value={variantForm.price} onChange={(e) => setVariantForm({ ...variantForm, price: e.target.value })} required /></label>
            </div>
            <label>Stock inicial <input type="number" min="0" value={variantForm.stock} onChange={(e) => setVariantForm({ ...variantForm, stock: e.target.value })} /></label>
            <button type="submit" className="btn btn-primary" style={{ marginTop: '0.75rem' }} disabled={loading}>Crear variante</button>
          </form>

          <div className="table-wrap">
            {selectedProduct ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Atributos</th>
                    <th>Costo</th>
                    <th>Precio</th>
                    <th>Stock</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {variants.map((v) => (
                    <tr key={v.id}>
                      <td><span className="font-mono" style={{ fontWeight: 700, fontSize: '0.8125rem' }}>{v.sku}</span></td>
                      <td>
                        {[v.color, v.size, v.custom_attribute].filter(Boolean).map((attr, i) => (
                          <span key={i} style={{ display: 'inline-block', background: '#f0f2ee', borderRadius: 4, padding: '1px 6px', fontSize: '0.75rem', marginRight: 4 }}>{attr}</span>
                        ))}
                      </td>
                      <td>${Number(v.cost).toLocaleString('es-CO')}</td>
                      <td style={{ fontWeight: 700 }}>${Number(v.price).toLocaleString('es-CO')}</td>
                      <td>
                        <span style={{ fontWeight: 700, color: v.stock === 0 ? '#991b1b' : v.stock < 5 ? '#854d0e' : '#166534' }}>
                          {v.stock}
                        </span>
                      </td>
                      <td><Badge variant={v.active ? 'success' : 'neutral'}>{v.active ? 'Activa' : 'Inactiva'}</Badge></td>
                    </tr>
                  ))}
                  {variants.length === 0 && (
                    <tr><td colSpan={6} className="state">Sin variantes para este producto</td></tr>
                  )}
                </tbody>
              </table>
            ) : (
              <div className="state">Selecciona un producto para ver sus variantes</div>
            )}
          </div>
        </div>
      )}

      {/* ── Inventory ── */}
      {tab === 'inventory' && (
        <div>
          {alerts.length > 0 && (
            <div className="alert warning" style={{ marginBottom: '1.25rem' }}>
              <AlertTriangle size={16} />
              <strong>{alerts.length} variante(s) con stock bajo o agotado. Revisa y registra entradas de inventario.</strong>
            </div>
          )}
          <div className="form-grid">
            <form className="form-panel" onSubmit={submitMovement}>
              <h3>Registrar movimiento</h3>
              <label>
                Variante *
                <select value={movementForm.variant_id} onChange={(e) => setMovementForm({ ...movementForm, variant_id: e.target.value })} required>
                  <option value="">Selecciona variante</option>
                  {allVariants.map((v) => (
                    <option key={v.id} value={v.id}>{v.product_name} — {v.sku} (stock: {v.stock})</option>
                  ))}
                </select>
              </label>
              <label>
                Tipo de movimiento
                <select value={movementForm.movement_type} onChange={(e) => setMovementForm({ ...movementForm, movement_type: e.target.value })}>
                  <option value="entrada">Entrada</option>
                  <option value="salida">Salida</option>
                  <option value="ajuste">Ajuste</option>
                </select>
              </label>
              <label>Cantidad * <input type="number" min="1" value={movementForm.quantity} onChange={(e) => setMovementForm({ ...movementForm, quantity: e.target.value })} required /></label>
              <label>Razón * <input value={movementForm.reason} onChange={(e) => setMovementForm({ ...movementForm, reason: e.target.value })} required /></label>
              <button type="submit" className="btn btn-primary" style={{ marginTop: '0.75rem' }} disabled={loading}>Registrar movimiento</button>
            </form>

            <div>
              <div style={{ marginBottom: '1rem', fontWeight: 700, fontSize: '0.9375rem', color: '#172026' }}>
                Alertas de stock mínimo
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr><th>Producto</th><th>SKU</th><th>Stock actual</th><th>Umbral mín.</th><th>Estado</th></tr>
                  </thead>
                  <tbody>
                    {alerts.length === 0 ? (
                      <tr><td colSpan={5} className="state">Sin alertas activas</td></tr>
                    ) : (
                      alerts.map((a) => (
                        <tr key={a.variant_id}>
                          <td><strong>{a.product_name}</strong></td>
                          <td className="font-mono" style={{ fontSize: '0.8125rem' }}>{a.sku}</td>
                          <td style={{ fontWeight: 800, color: a.stock === 0 ? '#991b1b' : '#854d0e' }}>{a.stock}</td>
                          <td>{a.threshold}</td>
                          <td>
                            <Badge variant={a.stock === 0 ? 'error' : 'warning'}>
                              {a.stock === 0 ? 'Agotado' : 'Stock bajo'}
                            </Badge>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
