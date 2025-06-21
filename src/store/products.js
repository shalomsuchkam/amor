import { create } from "zustand";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = "https://nyfngmkkcwoptlzycbuu.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im55Zm5nbWtrY3dvcHRsenljYnV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk5MDAwNzQsImV4cCI6MjA2NTQ3NjA3NH0.ATVhYEUtFUVyOJg-5hXxYMlqFrHI8-ao9OTxepVcMbQ";
export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export const useProductStore = create((set, get) => ({
  products: [],
  loading: false,
  error: null,

  fetchProducts: async () => {
    set({ loading: true });
    const { data, error } = await supabase.from("products").select("*").order("created_at", { ascending: false });
    set({ products: data || [], loading: false, error });
  },

  addProduct: async (prod) => {
    set({ loading: true });
    const { error } = await supabase.from("products").insert([prod]);
    if (!error) await get().fetchProducts();
    set({ loading: false, error });
  },

  editProduct: async (id, updates) => {
    set({ loading: true });
    const { error } = await supabase.from("products").update(updates).eq("id", id);
    if (!error) await get().fetchProducts();
    set({ loading: false, error });
  },

  deleteProduct: async (id) => {
    set({ loading: true });
    const { error } = await supabase.from("products").delete().eq("id", id);
    if (!error) await get().fetchProducts();
    set({ loading: false, error });
  },
}));
