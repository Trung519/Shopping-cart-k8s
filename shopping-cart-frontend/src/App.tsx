import { Routes, Route } from 'react-router-dom'
import { useAppAuth } from './contexts/AuthContext'
import Layout from './components/layout/Layout'
import HomePage from './pages/HomePage'
import ProductsPage from './pages/ProductsPage'
import ProductDetailPage from './pages/ProductDetailPage'
import ProductAdminPage from './pages/ProductAdminPage'
import AdminUsersPage from './pages/AdminUsersPage'
import CartPage from './pages/CartPage'
import OrdersPage from './pages/OrdersPage'
import OrderDetailPage from './pages/OrderDetailPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import ProtectedRoute from './components/layout/ProtectedRoute'
import LoadingSpinner from './components/ui/LoadingSpinner'
import WorkspaceLayout from './components/layout/WorkspaceLayout'
import CheckoutPage from './pages/CheckoutPage'
import BuyerOverviewPage from './pages/buyer/BuyerOverviewPage'
import WishlistPage from './pages/buyer/WishlistPage'
import NotificationsPage from './pages/buyer/NotificationsPage'
import SellerDashboardPage from './pages/seller/SellerDashboardPage'
import SellerProductsPage from './pages/seller/SellerProductsPage'
import AdminDashboardPage from './pages/admin/AdminDashboardPage'
import AdminSellersPage from './pages/admin/AdminSellersPage'
import AdminOrdersPage from './pages/admin/AdminOrdersPage'
import AdminCategoriesPage from './pages/admin/AdminCategoriesPage'
import WorkspacePlaceholderPage from './pages/WorkspacePlaceholderPage'
import SupportPage from './pages/SupportPage'
import OperationsDemo from './pages/admin/OperationsDemo'
import ShopDemoApp from './demo/buyer/ShopDemoApp'

function App() {
  const auth = useAppAuth()

  if (auth.isLoading && !window.location.pathname.startsWith('/demo/')) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/demo/admin" element={<OperationsDemo />} />
      <Route path="/demo/admin/:section" element={<OperationsDemo />} />
      <Route path="/demo/shop/*" element={<ShopDemoApp />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="products/:id" element={<ProductDetailPage />} />
        <Route path="support" element={<SupportPage />} />
        <Route
          path="cart"
          element={
            <ProtectedRoute>
              <CartPage />
            </ProtectedRoute>
          }
        />
        <Route path="checkout" element={<ProtectedRoute><CheckoutPage /></ProtectedRoute>} />
        <Route
          path="orders"
          element={
            <ProtectedRoute>
              <OrdersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="orders/:id"
          element={
            <ProtectedRoute>
              <OrderDetailPage />
            </ProtectedRoute>
          }
        />
        <Route path="buyer" element={<ProtectedRoute><WorkspaceLayout kind="buyer" /></ProtectedRoute>}>
          <Route index element={<BuyerOverviewPage />} />
          <Route path="wishlist" element={<WishlistPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="addresses" element={<WorkspacePlaceholderPage />} />
        </Route>
        <Route path="seller" element={<ProtectedRoute><WorkspaceLayout kind="seller" /></ProtectedRoute>}>
          <Route index element={<SellerDashboardPage />} />
          <Route path="products" element={<ProtectedRoute requiredRoles={['seller-owner', 'seller-manager', 'seller-staff']}><SellerProductsPage /></ProtectedRoute>} />
          <Route path="products/new" element={<ProtectedRoute requiredRoles={['seller-owner', 'seller-manager']}><ProductAdminPage /></ProtectedRoute>} />
          <Route path="products/:id/edit" element={<ProtectedRoute requiredRoles={['seller-owner', 'seller-manager']}><ProductAdminPage /></ProtectedRoute>} />
          <Route path="inventory" element={<WorkspacePlaceholderPage />} />
          <Route path="orders" element={<WorkspacePlaceholderPage />} />
          <Route path="promotions" element={<WorkspacePlaceholderPage />} />
          <Route path="messages" element={<WorkspacePlaceholderPage />} />
          <Route path="finance" element={<WorkspacePlaceholderPage />} />
          <Route path="settings" element={<WorkspacePlaceholderPage />} />
        </Route>
        <Route path="admin" element={<ProtectedRoute requiredRoles={['admin', 'platform-admin', 'cart-admin', 'user-admin', 'seller-reviewer', 'catalog-moderator', 'order-operator', 'finance-operator', 'support-agent']}><WorkspaceLayout kind="admin" /></ProtectedRoute>}>
          <Route index element={<AdminDashboardPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="sellers" element={<AdminSellersPage />} />
          <Route path="products/new" element={<ProductAdminPage />} />
          <Route path="products/:id/edit" element={<ProductAdminPage />} />
          <Route path="catalog" element={<ProtectedRoute requiredRoles={['admin', 'platform-admin', 'cart-admin', 'catalog-admin']}><AdminCategoriesPage /></ProtectedRoute>} />
          <Route path="orders" element={<AdminOrdersPage />} />
          <Route path="returns" element={<WorkspacePlaceholderPage />} />
          <Route path="finance" element={<WorkspacePlaceholderPage />} />
          <Route path="analytics" element={<WorkspacePlaceholderPage />} />
          <Route path="audit" element={<WorkspacePlaceholderPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
