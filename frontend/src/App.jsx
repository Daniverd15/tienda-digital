import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import { AuthProvider } from './context/AuthContext';
import AdminOrders from './pages/AdminOrders';
import AdminCatalog from './pages/AdminCatalog';
import AdminFinance from './pages/AdminFinance';
import AdminHome from './pages/AdminHome';
import Catalog from './pages/Catalog';
import Cart from './pages/Cart';
import Checkout from './pages/Checkout';
import Home from './pages/Home';
import Login from './pages/Login';
import MyOrders from './pages/MyOrders';
import Notifications from './pages/Notifications';
import OrderDetail from './pages/OrderDetail';
import Placeholder from './pages/Placeholder';
import PaymentResult from './pages/PaymentResult';
import ProductDetail from './pages/ProductDetail';
import Register from './pages/Register';
import ProtectedRoute from './routes/ProtectedRoute';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/registro" element={<Register />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/carrito" element={<Cart />} />
            <Route path="/checkout" element={<Checkout />} />
            <Route path="/pago" element={<PaymentResult />} />
            <Route path="/mis-pedidos" element={<MyOrders />} />
            <Route path="/pedidos/:id" element={<OrderDetail />} />
            <Route path="/notificaciones" element={<Notifications />} />
          </Route>
          <Route element={<ProtectedRoute role="admin" />}>
            <Route path="/admin" element={<AdminHome />} />
            <Route path="/admin/catalogo" element={<AdminCatalog />} />
            <Route path="/admin/finanzas" element={<AdminFinance />} />
            <Route path="/admin/pedidos" element={<AdminOrders />} />
          </Route>
          <Route path="/catalogo" element={<Catalog />} />
          <Route path="/productos/:id" element={<ProductDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
