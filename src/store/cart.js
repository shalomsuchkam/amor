import { create } from "zustand";

const CART_KEY = "cart";
const getCart = () => {
  try {
    return JSON.parse(localStorage.getItem(CART_KEY)) || [];
  } catch { return []; }
};

export const useCartStore = create((set, get) => ({
  cart: getCart(),
  addToCart: (item) => {
    const exists = get().cart.find(x => x.id === item.id);
    const newCart = exists
      ? get().cart.map(x => x.id === item.id ? {...x, qty: x.qty + 1} : x)
      : [...get().cart, { ...item, qty: 1 }];
    localStorage.setItem(CART_KEY, JSON.stringify(newCart));
    set({ cart: newCart });
  },
  removeFromCart: (id) => {
    const newCart = get().cart.filter(x => x.id !== id);
    localStorage.setItem(CART_KEY, JSON.stringify(newCart));
    set({ cart: newCart });
  },
  changeQty: (id, qty) => {
    const newCart = get().cart.map(x =>
      x.id === id ? { ...x, qty: Math.max(1, qty) } : x
    );
    localStorage.setItem(CART_KEY, JSON.stringify(newCart));
    set({ cart: newCart });
  },
  clearCart: () => {
    localStorage.removeItem(CART_KEY);
    set({ cart: [] });
  }
}));
