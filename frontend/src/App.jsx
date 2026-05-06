import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import { AuthProvider } from './context/AuthContext';
import Catalog from './pages/Catalog';
import Home from './pages/Home';
import Login from './pages/Login';
import Placeholder from './pages/Placeholder';
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
            <Route path="/carrito" element={<Placeholder title="Carrito" />} />
            <Route path="/mis-pedidos" element={<Placeholder title="Mis pedidos" />} />
          </Route>
          <Route element={<ProtectedRoute role="admin" />}>
            <Route path="/admin" element={<Placeholder title="Panel administrativo" />} />
          </Route>
          <Route path="/catalogo" element={<Catalog />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
