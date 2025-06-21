import { Link, NavLink } from "react-router-dom";
import { useCartStore } from "../store/cart.js";
import logo from "../../logo.png";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./Header.css";

function useHideOnScroll() {
  const [visible, setVisible] = useState(true);
  const lastScroll = useRef(window.scrollY);

  useEffect(() => {
    const onScroll = () => {
      const curr = window.scrollY;
      if (curr < 80) return setVisible(true);
      setVisible(curr < lastScroll.current);
      lastScroll.current = curr;
    };
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return visible;
}

function Header() {
  const cartCount = useCartStore((s) => s.cart.reduce((acc, x) => acc + x.qty, 0));
  const [open, setOpen] = useState(false);
  const visible = useHideOnScroll();

  // Для свайпа по бургер-меню (закрытие по свайпу вправо)
  const menuRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    let startX = null;

    const onTouchStart = (e) => {
      startX = e.touches[0].clientX;
    };
    const onTouchMove = (e) => {
      if (startX === null) return;
      const diffX = e.touches[0].clientX - startX;
      if (diffX > 50) setOpen(false);
    };
    const menu = menuRef.current;
    if (menu) {
      menu.addEventListener("touchstart", onTouchStart);
      menu.addEventListener("touchmove", onTouchMove);
    }
    return () => {
      if (menu) {
        menu.removeEventListener("touchstart", onTouchStart);
        menu.removeEventListener("touchmove", onTouchMove);
      }
    };
  }, [open]);

  // Блокировка прокрутки подложки при открытом меню
  useEffect(() => {
    if (open) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.header
          initial={{ y: -70 }}
          animate={{ y: 0 }}
          exit={{ y: -70 }}
          transition={{ duration: 0.35 }}
          className="amor-header"
        >
          <div className="amor-header-inner">
            {/* Логотип и название */}
            <Link to="/" className="amor-logo-link">
              <img src={logo} alt="Amor Flowers" className="amor-logo" />
              <span className="amor-title">
                Amor Flowers
              </span>
            </Link>
            {/* Desktop menu */}
            <nav className="amor-nav">
              <NavLink to="/" className={({isActive}) => isActive ? "active" : undefined}>
                Главная <span>🏡</span>
              </NavLink>
              <NavLink to="/catalog" className={({isActive}) => isActive ? "active" : undefined}>
                Каталог <span>💐</span>
              </NavLink>
              <NavLink to="/about" className={({isActive}) => isActive ? "active" : undefined}>
                О нас <span>💖</span>
              </NavLink>
              <NavLink to="/delivery" className={({isActive}) => isActive ? "active" : undefined}>
                Доставка <span>🚗</span>
              </NavLink>
              <NavLink to="/contacts" className={({isActive}) => isActive ? "active" : undefined}>
                Контакты <span>📱</span>
              </NavLink>
            </nav>
            {/* Корзина и бургер */}
            <div className="amor-cart-burger">
              <Link to="/cart" className="amor-cart-link">
                <span className="cart-icon">🛒</span>
                <span className="cart-label">Корзина</span>
                <AnimatePresence>
                  {cartCount > 0 && (
                    <motion.span
                      key={cartCount}
                      initial={{ scale: 0.7, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.7, opacity: 0 }}
                      className="amor-cart-badge"
                    >
                      {cartCount}
                    </motion.span>
                  )}
                </AnimatePresence>
              </Link>
              {/* Бургер — только на мобильных */}
              <button
                className={`amor-burger ${open ? "open" : ""}`}
                onClick={() => setOpen(!open)}
                aria-label="Открыть меню"
              >
                <span />
                <span />
                <span />
              </button>
            </div>
            {/* Мобильное меню */}
            <AnimatePresence>
              {open && (
                <>
                  <motion.div
                    key="overlay"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.48 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="amor-menu-overlay"
                    onClick={() => setOpen(false)}
                  />
                  <motion.nav
                    ref={menuRef}
                    initial={{ x: 260 }}
                    animate={{ x: 0 }}
                    exit={{ x: 260 }}
                    transition={{ type: "spring", stiffness: 340, damping: 28 }}
                    className="amor-mobile-menu"
                  >
                    <button
                      className="amor-menu-close"
                      onClick={() => setOpen(false)}
                      aria-label="Закрыть меню"
                    >
                      &times;
                    </button>
                    <div className="amor-mobile-links">
                      <NavLink to="/" onClick={() => setOpen(false)}>Главная 🏡</NavLink>
                      <NavLink to="/catalog" onClick={() => setOpen(false)}>Каталог 💐</NavLink>
                      <NavLink to="/about" onClick={() => setOpen(false)}>О нас 💖</NavLink>
                      <NavLink to="/delivery" onClick={() => setOpen(false)}>Доставка 🚗</NavLink>
                      <NavLink to="/contacts" onClick={() => setOpen(false)}>Контакты 📱</NavLink>
                      <Link to="/cart" className="amor-mobile-cart" onClick={() => setOpen(false)}>
                        🛒 Корзина
                        {cartCount > 0 && (
                          <span className="amor-cart-badge">{cartCount}</span>
                        )}
                      </Link>
                    </div>
                  </motion.nav>
                </>
              )}
            </AnimatePresence>
          </div>
        </motion.header>
      )}
    </AnimatePresence>
  );
}

export default Header;
