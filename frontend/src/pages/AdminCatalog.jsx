import { useEffect, useState } from 'react';
import api from '../api/client';

const emptyCategory = { name: '', description: '', active: true, archived: false };
const emptyProduct = {
  category_id: '',
  name: '',
  description: '',
  long_description: '',
  base_price: '',
  published: true,
  archived: false,
  image_url: ''
};
const emptyVariant = {
  sku: '',
  color: '',
  size: '',
  custom_attribute: '',
  cost: '',
  price: '',
  stock: 0,
  reserved_stock: 0,
  active: true
};
const emptyMovement = { variant_id: '', movement_type: 'entrada', quantity: 1, reason: '' };

export default function AdminCatalog() {
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [variants, setVariants] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [categoryForm, setCategoryForm] = useState(emptyCategory);
  const [productForm, setProductForm] = useState(emptyProduct);
  const [variantForm, setVariantForm] = useState(emptyVariant);
  const [movementForm, setMovementForm] = useState(emptyMovement);
  const [message, setMessage] = useState('');

  const load = async () => {
    const [categoryRes, productRes, alertRes] = await Promise.all([
      api.get('/admin/categories'),
      api.get('/admin/products'),
      api.get('/admin/inventory/alerts')
    ]);
    setCategories(categoryRes.data);
    setProducts(productRes.data);
    setAlerts(alertRes.data);
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!selectedProduct) return;
    api.get(`/admin/products/${selectedProduct}/variants`).then(({ data }) => setVariants(data));
  }, [selectedProduct]);

  const submitCategory = async (event) => {
    event.preventDefault();
    await api.post('/admin/categories', categoryForm);
    setCategoryForm(emptyCategory);
    setMessage('Categoria creada.');
    load();
  };

  const submitProduct = async (event) => {
    event.preventDefault();
    await api.post('/admin/products', { ...productForm, category_id: Number(productForm.category_id), base_price: Number(productForm.base_price) });
    setProductForm(emptyProduct);
    setMessage('Producto creado.');
    load();
  };

  const submitVariant = async (event) => {
    event.preventDefault();
    await api.post(`/admin/products/${selectedProduct}/variants`, {
      ...variantForm,
      cost: Number(variantForm.cost),
      price: Number(variantForm.price),
      stock: Number(variantForm.stock),
      reserved_stock: Number(variantForm.reserved_stock)
    });
    setVariantForm(emptyVariant);
    setMessage('Variante creada.');
    const { data } = await api.get(`/admin/products/${selectedProduct}/variants`);
    setVariants(data);
    load();
  };

  const submitMovement = async (event) => {
    event.preventDefault();
    await api.post('/admin/inventory/movements', {
      ...movementForm,
      variant_id: Number(movementForm.variant_id),
      quantity: Number(movementForm.quantity)
    });
    setMovementForm(emptyMovement);
    setMessage('Movimiento registrado.');
    load();
  };

  return (
    <main className="page-shell admin-grid-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">RF-07</span>
          <h1>Catalogo e inventario</h1>
        </div>
      </div>
      {message && <p className="alert success">{message}</p>}
      <section className="admin-section">
        <form onSubmit={submitCategory}>
          <h2>Categorias</h2>
          <input placeholder="Nombre" value={categoryForm.name} onChange={(event) => setCategoryForm({ ...categoryForm, name: event.target.value })} required />
          <input placeholder="Descripcion" value={categoryForm.description} onChange={(event) => setCategoryForm({ ...categoryForm, description: event.target.value })} />
          <button className="primary-button">Crear categoria</button>
        </form>
        <div className="table-list">
          {categories.map((category) => (
            <article className="row-card" key={category.id}>
              <strong>{category.name}</strong>
              <span>{category.active ? 'Activa' : 'Inactiva'}</span>
              <span>{category.archived ? 'Archivada' : 'Publicable'}</span>
            </article>
          ))}
        </div>
      </section>
      <section className="admin-section">
        <form onSubmit={submitProduct}>
          <h2>Productos</h2>
          <select value={productForm.category_id} onChange={(event) => setProductForm({ ...productForm, category_id: event.target.value })} required>
            <option value="">Categoria</option>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <input placeholder="Nombre" value={productForm.name} onChange={(event) => setProductForm({ ...productForm, name: event.target.value })} required />
          <input placeholder="Descripcion" value={productForm.description} onChange={(event) => setProductForm({ ...productForm, description: event.target.value })} required />
          <input placeholder="Precio base" type="number" value={productForm.base_price} onChange={(event) => setProductForm({ ...productForm, base_price: event.target.value })} required />
          <input placeholder="Imagen URL" value={productForm.image_url} onChange={(event) => setProductForm({ ...productForm, image_url: event.target.value })} />
          <button className="primary-button">Crear producto</button>
        </form>
        <div className="table-list">
          {products.map((product) => (
            <button className="row-card row-button" key={product.id} onClick={() => setSelectedProduct(product.id)}>
              <strong>{product.name}</strong>
              <span>{product.category_name}</span>
              <span>{product.published ? 'Publicado' : 'Oculto'}</span>
              <span>{product.stock} unidades</span>
            </button>
          ))}
        </div>
      </section>
      <section className="admin-section">
        <form onSubmit={submitVariant}>
          <h2>Variantes</h2>
          <select value={selectedProduct} onChange={(event) => setSelectedProduct(event.target.value)} required>
            <option value="">Producto</option>
            {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
          </select>
          {['sku', 'color', 'size', 'custom_attribute', 'cost', 'price', 'stock'].map((field) => (
            <input
              key={field}
              placeholder={field}
              type={['cost', 'price', 'stock'].includes(field) ? 'number' : 'text'}
              value={variantForm[field]}
              onChange={(event) => setVariantForm({ ...variantForm, [field]: event.target.value })}
              required={['sku', 'cost', 'price', 'stock'].includes(field)}
            />
          ))}
          <button className="primary-button">Crear variante</button>
        </form>
        <div className="table-list">
          {variants.map((variant) => (
            <article className="row-card" key={variant.id}>
              <strong>{variant.sku}</strong>
              <span>{variant.color || variant.size || variant.custom_attribute}</span>
              <span>Stock {variant.stock}</span>
              <span>${Number(variant.price).toLocaleString('es-CO')}</span>
            </article>
          ))}
        </div>
      </section>
      <section className="admin-section">
        <form onSubmit={submitMovement}>
          <h2>Inventario</h2>
          <select value={movementForm.variant_id} onChange={(event) => setMovementForm({ ...movementForm, variant_id: event.target.value })} required>
            <option value="">Variante</option>
            {products.flatMap((product) => product.variants || []).map((variant) => (
              <option key={variant.id} value={variant.id}>{variant.sku}</option>
            ))}
          </select>
          <select value={movementForm.movement_type} onChange={(event) => setMovementForm({ ...movementForm, movement_type: event.target.value })}>
            <option value="entrada">Entrada</option>
            <option value="salida">Salida</option>
            <option value="ajuste">Ajuste</option>
          </select>
          <input type="number" min="1" value={movementForm.quantity} onChange={(event) => setMovementForm({ ...movementForm, quantity: event.target.value })} />
          <input placeholder="Razon" value={movementForm.reason} onChange={(event) => setMovementForm({ ...movementForm, reason: event.target.value })} required />
          <button className="primary-button">Registrar movimiento</button>
        </form>
        <div className="table-list">
          <h2>Alertas de stock</h2>
          {alerts.map((alert) => (
            <article className="row-card" key={alert.variant_id}>
              <strong>{alert.product_name}</strong>
              <span>{alert.sku}</span>
              <span>Stock {alert.stock}</span>
              <span>Umbral {alert.threshold}</span>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

