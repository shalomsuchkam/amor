import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Header from "./layout/Header.jsx";
import Footer from "./layout/Footer.jsx";
import Home from "./pages/Home.jsx";
import Catalog from "./pages/Catalog.jsx";
import About from "./pages/About.jsx";
import Delivery from "./pages/Delivery.jsx";
import Contacts from "./pages/Contacts.jsx";
import Cart from "./pages/Cart.jsx";
import AdminPanel from "./components/AdminPanel.jsx"; // <--- замени на новый компонент
import "./App.css";

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-col bg-amor-pink font-decor">
        <Header />
        <div className="pt-[70px] sm:pt-[82px]" />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/catalog" element={<Catalog />} />
            <Route path="/about" element={<About />} />
            <Route path="/delivery" element={<Delivery />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/cart" element={<Cart />} />
            <Route path="/admin" element={<AdminPanel />} /> {/* исправлено */}
          </Routes>
        </main>
        <Footer />
      </div>
    </Router>
  );
}

export default App;
