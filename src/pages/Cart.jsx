import { useCartStore } from "../store/cart.js";
import { useState } from "react";

function Cart() {
  const { cart, removeFromCart, clearCart } = useCartStore();
  const [showOrder, setShowOrder] = useState(false);

  const total = cart.reduce((sum, item) => sum + item.price * item.qty, 0);

  return (
    <section className="form-block" style={{maxWidth: 700, margin: "44px auto 32px"}}>
      <h1 style={{fontSize: "2rem", fontWeight: 900, color: "#ef5da8", textAlign: "center", marginBottom: 30}}>Корзина</h1>

      {cart.length === 0 ? (
        <div style={{textAlign: "center", fontSize: 18, color: "#914d0a", marginBottom: 24}}>
          Ваша корзина пуста!
        </div>
      ) : (
        <>
          <table className="table-list">
            <thead>
              <tr>
                <th>Фото</th>
                <th>Название</th>
                <th>Кол-во</th>
                <th>Цена</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cart.map((item, idx) => (
                <tr key={item.id || idx}>
                  <td>
                    <img
                      src={item.image_url}
                      alt={item.title}
                      style={{width: 56, height: 56, objectFit: "cover"}}
                    />
                  </td>
                  <td>{item.title}</td>
                  <td>{item.qty}</td>
                  <td>{item.price} ₸</td>
                  <td>
                    <button
                      style={{
                        background: "#ffe5f1",
                        color: "#ef5da8",
                        borderRadius: 10,
                        padding: "6px 15px",
                        fontWeight: 700,
                        border: "none",
                        cursor: "pointer",
                        boxShadow: "0 1px 8px 0 rgba(233, 30, 99, 0.08)"
                      }}
                      onClick={() => removeFromCart(item.id)}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            marginTop: 24, flexWrap: "wrap", gap: 10
          }}>
            <div style={{fontWeight: 900, fontSize: 18, color: "#ef5da8"}}>
              Итого: {total} ₸
            </div>
            <div>
              <button
                style={{marginRight: 10, background: "#ffe5f1", color: "#ef5da8"}}
                onClick={clearCart}
              >
                Очистить корзину
              </button>
              <button
                style={{}}
                onClick={() => setShowOrder(true)}
              >
                Оформить заказ
              </button>
            </div>
          </div>
        </>
      )}

      {showOrder && (
        <div
          style={{
            position: "fixed",
            zIndex: 1001,
            inset: 0,
            background: "rgba(0,0,0,0.18)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16
          }}
        >
          <form
            style={{
              background: "#fff",
              borderRadius: 24,
              boxShadow: "0 2px 32px 0 rgba(233,30,99,0.13)",
              padding: "32px 20px",
              minWidth: 320,
              maxWidth: 390,
              width: "100%",
              position: "relative"
            }}
            onSubmit={e => {
              e.preventDefault();
              alert("Заявка оформлена! Наш флорист свяжется с вами.");
              setShowOrder(false);
              clearCart();
            }}
          >
            <button
              type="button"
              onClick={() => setShowOrder(false)}
              style={{
                position: "absolute", top: 12, right: 20,
                fontSize: 30, color: "#ef5da8", background: "none",
                border: "none", cursor: "pointer"
              }}
            >&times;</button>
            <div className="font-bold" style={{fontSize: "1.08rem", color: "#ef5da8", marginBottom: 20, textAlign: "center"}}>
              Оформление заказа
            </div>
            <label>Ваше имя</label>
            <input type="text" required />
            <label>Телефон</label>
            <input type="text" required placeholder="+7..." />
            <label>Комментарий (необязательно)</label>
            <textarea style={{minHeight: 60}} />
            <button type="submit" style={{marginTop: 16}}>Отправить заявку</button>
          </form>
        </div>
      )}
    </section>
  );
}

export default Cart;
