import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import AdminAudit from './pages/AdminAudit';
import AdminCatalog from './pages/AdminCatalog';
import AdminCustomers from './pages/AdminCustomers';
import AdminFinance from './pages/AdminFinance';
import AdminHome from './pages/AdminHome';
import AdminOrders from './pages/AdminOrders';
import AdminSettings from './pages/AdminSettings';
import Catalog from './pages/Catalog';
import Cart from './pages/Cart';
import Checkout from './pages/Checkout';
import CreateReview from './pages/CreateReview';
import Home from './pages/Home';
import Login from './pages/Login';
import MyOrders from './pages/MyOrders';
import Notifications from './pages/Notifications';
import OrderDetail from './pages/OrderDetail';
import PaymentResult from './pages/PaymentResult';
import ProductDetail from './pages/ProductDetail';
import Register from './pages/Register';
import ProtectedRoute from './routes/ProtectedRoute';

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Navbar />
          <Routes>
            {/* Public */}
            <Route path="/"              element={<Home />} />
            <Route path="/login"         element={<Login />} />
            <Route path="/registro"      element={<Register />} />
            <Route path="/catalogo"      element={<Catalog />} />
            <Route path="/productos/:id" element={<ProductDetail />} />

            {/* Customer authenticated */}
            <Route element={<ProtectedRoute />}>
              <Route path="/carrito"                          element={<Cart />} />
              <Route path="/checkout"                         element={<Checkout />} />
              <Route path="/pago"                             element={<PaymentResult />} />
              <Route path="/mis-pedidos"                      element={<MyOrders />} />
              <Route path="/pedidos/:id"                      element={<OrderDetail />} />
              <Route path="/notificaciones"                   element={<Notifications />} />
              <Route path="/resenas/:orderId/:productId"      element={<CreateReview />} />
            </Route>

            {/* Admin */}
            <Route element={<ProtectedRoute role="admin" />}>
              <Route path="/admin"                  element={<AdminHome />} />
              <Route path="/admin/pedidos"          element={<AdminOrders />} />
              <Route path="/admin/clientes"         element={<AdminCustomers />} />
              <Route path="/admin/catalogo"         element={<AdminCatalog />} />
              <Route path="/admin/finanzas"         element={<AdminFinance />} />
              <Route path="/admin/configuracion"    element={<AdminSettings />} />
              <Route path="/admin/auditoria"        element={<AdminAudit />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
