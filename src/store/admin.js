import { create } from "zustand";

const ADMIN_PASS = "amor2024"; // Можешь сменить

export const useAdminStore = create((set) => ({
  isAuth: localStorage.getItem("isAdmin") === "1",
  login: (pw) => {
    if (pw === ADMIN_PASS) {
      set({ isAuth: true });
      localStorage.setItem("isAdmin", "1");
      return true;
    }
    return false;
  },
  logout: () => {
    set({ isAuth: false });
    localStorage.removeItem("isAdmin");
  },
}));
