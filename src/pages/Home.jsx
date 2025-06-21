import { useProductStore } from "../store/products.js";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useCartStore } from "../store/cart.js";
import { motion, AnimatePresence } from "framer-motion";
import OrderModal from "../components/OrderModal.jsx";

// Получение случайных товаров
function getRandomItems(arr, count) {
  if (arr.length <= count) return arr;
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
}

function Home() {
  const { products, fetchProducts, loading } = useProductStore();
  const addToCart = useCartStore((s) => s.addToCart);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  // Сколько товаров показывать в рекомендации (адаптивно)
  const [recCount, setRecCount] = useState(
    window.innerWidth < 480 ? 1 : window.innerWidth < 768 ? 2 : 3
  );

  const [recSet, setRecSet] = useState(getRandomItems(products, recCount));
  const [recKey, setRecKey] = useState(0);

  useEffect(() => {
    fetchProducts();
    // eslint-disable-next-line
  }, []);

  useEffect(() => {
    if (products.length === 0) return;
    setRecSet(getRandomItems(products, recCount));
  }, [products, recCount]);

  useEffect(() => {
    if (products.length === 0) return;
    const interval = setInterval(() => {
      setRecSet(getRandomItems(products, recCount));
      setRecKey(k => k + 1);
    }, 4000);
    return () => clearInterval(interval);
  }, [products, recCount]);

  useEffect(() => {
    function onResize() {
      const count =
        window.innerWidth < 480 ? 1 :
        window.innerWidth < 768 ? 2 : 3;
      setRecCount(count);
      setRecSet(getRandomItems(products, count));
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [products]);

  return (
    <div>
      {/* Premium баннер с анимацией */}
      <motion.section
        initial={{ opacity: 0, y: 50 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, type: "spring" }}
        style={{
          maxWidth: 950,
          margin: "64px auto 48px",
          background: "linear-gradient(97deg, #ffe5f1 65%, #fff0f7 100%)",
          boxShadow: "0 8px 32px 0 rgba(233,30,99,0.11)",
          borderRadius: 32,
          padding: "44px 18px 48px 18px",
          textAlign: "center"
        }}
      >
        <h1 style={{
          fontSize: "2.4rem", color: "#ef5da8", fontWeight: 900,
          marginBottom: 18, fontFamily: "inherit"
        }}>
          Премиальные букеты <br /> для особых моментов жизни
        </h1>
        <p style={{
          fontSize: 21, color: "#62284c", fontWeight: 500,
          marginBottom: 30, lineHeight: 1.5
        }}>
          <span style={{color:"#ef5da8", fontWeight:700}}>Amor Flowers</span> — место, где букеты становятся искусством.
          <br />
          Лучшие свежие цветы, авторские композиции, ручная работа и&nbsp;
          <span style={{background:"#ffe5f1", padding:"1px 7px", borderRadius:7}}>эксклюзивное обслуживание</span>.
          <br />
          Доставка по Алматы 24/7. Бесплатная консультация флориста.
        </p>
        <div>
          <Link
            to="/catalog"
            style={{
              padding: "16px 48px",
              borderRadius: 27,
              fontWeight: 700,
              background: "linear-gradient(90deg,#ef5da8,#efb2d7 80%)",
              color: "#fff",
              textDecoration: "none",
              fontSize: 20,
              boxShadow: "0 2px 16px 0 rgba(233,30,99,0.09)",
              transition: "background 0.2s"
            }}
          >
            Перейти в каталог
          </Link>
        </div>
      </motion.section>

      {/* Рекомендуемое (анимированное) */}
      <motion.section
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65 }}
        style={{
          maxWidth: 1000,
          margin: "0 auto 40px",
          background: "#fff",
          boxShadow: "0 4px 24px 0 rgba(233,30,99,0.09)",
          borderRadius: 32,
          padding: "34px 16px"
        }}
      >
        <h2 style={{
          fontSize: "1.7rem",
          color: "#ef5da8",
          fontWeight: 900,
          textAlign: "center",
          marginBottom: 28
        }}>
          Рекомендуемое
        </h2>
        <AnimatePresence mode="wait">
          <motion.div
            key={recKey}
            initial={{ opacity: 0, scale: 0.97, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 24 }}
            transition={{ duration: 0.5 }}
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${recCount}, 1fr)`,
              gap: "30px 34px",
              justifyItems: "center"
            }}
          >
            {recSet.map((item, idx) => (
              <div
                key={item.id || idx}
                className="card"
                style={{minWidth:220, maxWidth:320, width:"100%"}}
              >
                <img
                  src={item.image_url}
                  alt={item.title}
                  style={{width:"100%", height:"180px", objectFit:"cover", marginBottom:8}}
                />
                <div style={{
                  fontWeight:700, fontSize: "1.08rem",
                  color:"#ef5da8", textAlign:"center", marginBottom:5
                }}>{item.title}</div>
                <div style={{
                  fontWeight:900, color:"#2d233b", fontSize:17, marginBottom:10
                }}>{item.price} ₸</div>
                <div style={{display:"flex", gap:10, justifyContent:"center"}}>
                  <button
                    onClick={() => {
                      setSelectedProduct(item);
                      setModalOpen(true);
                    }}
                    style={{padding:"10px 20px"}}
                  >
                    Купить
                  </button>
                  <button
                    onClick={() => addToCart(item)}
                    style={{
                      background: "#fff",
                      color: "#ef5da8",
                      border: "1.5px solid #efb2d7",
                      fontWeight: 700,
                      padding: "10px 20px",
                      borderRadius: "14px",
                      marginLeft: 4
                    }}
                  >
                    В корзину
                  </button>
                </div>
              </div>
            ))}
          </motion.div>
        </AnimatePresence>
      </motion.section>

      {/* Модалка заказа */}
      <OrderModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        productsInCart={selectedProduct ? [{ ...selectedProduct, qty: 1 }] : []}
      />
    </div>
  );
}

export default Home;
