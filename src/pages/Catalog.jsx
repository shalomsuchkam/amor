import React, { useState, useEffect } from "react";
import COLORS from "../data/colors";
import OCCASIONS from "../data/occasions";
import FLOWER_TYPES from "../data/flowers";
import { supabase } from "../supabaseClient";
import "./Catalog.css";

export default function Catalog() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [color, setColor] = useState("");
  const [occasion, setOccasion] = useState("");
  const [type, setType] = useState("");

  useEffect(() => {
    async function fetchProducts() {
      setLoading(true);
      setError("");
      const { data, error } = await supabase.from("products").select("*");
      if (error) setError("Ошибка загрузки букетов");
      else setProducts(data || []);
      setLoading(false);
    }
    fetchProducts();
  }, []);

  // Фильтрация
  const filtered = products.filter((product) => {
    const matchesSearch =
      !search ||
      (product.title && product.title.toLowerCase().includes(search.toLowerCase())) ||
      (product.description && product.description.toLowerCase().includes(search.toLowerCase()));

    // Цвета — сравниваем по имени
    const matchesColor =
      !color ||
      (product.colors &&
        product.colors.some((c) =>
          typeof c === "string" ? c === color : c.name === color
        ));

    // Поводы и типы — сравниваем по строке
    const matchesOccasion =
      !occasion ||
      (product.occasions &&
        product.occasions.some((o) => o === occasion));

    const matchesType =
      !type ||
      (product.types &&
        product.types.some((t) => t === type));

    return matchesSearch && matchesColor && matchesOccasion && matchesType;
  });

  return (
    <div className="catalog-root">
      <div className="catalog-filters">
        <input
          className="catalog-search"
          placeholder="Поиск по названию или описанию…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />

        <div className="catalog-dropdown-wrap">
          <select className="catalog-dropdown" value={color} onChange={e => setColor(e.target.value)}>
            <option value="">Цвет</option>
            {COLORS.map((c) =>
              <option key={c.name} value={c.name}>{c.name}</option>
            )}
          </select>
          <span className="catalog-dropdown-arrow">▼</span>
        </div>

        <div className="catalog-dropdown-wrap">
          <select className="catalog-dropdown" value={occasion} onChange={e => setOccasion(e.target.value)}>
            <option value="">Повод</option>
            {OCCASIONS.map((o) =>
              <option key={o} value={o}>{o}</option>
            )}
          </select>
          <span className="catalog-dropdown-arrow">▼</span>
        </div>

        <div className="catalog-dropdown-wrap">
          <select className="catalog-dropdown" value={type} onChange={e => setType(e.target.value)}>
            <option value="">Тип цветов</option>
            {FLOWER_TYPES.map((f) =>
              <option key={f} value={f}>{f}</option>
            )}
          </select>
          <span className="catalog-dropdown-arrow">▼</span>
        </div>
      </div>

      {loading && <div className="catalog-loader">Загрузка букетов...</div>}
      {error && <div className="catalog-error">{error}</div>}

      <div className="catalog-list">
        {!loading && !error && filtered.length === 0 && (
          <div className="catalog-empty">Нет букетов по вашему запросу 😕</div>
        )}
        {filtered.map((product) => (
          <div className="catalog-card" key={product.id}>
            <div className="catalog-img-wrap">
              <img src={product.image} alt={product.title} />
            </div>
            <div className="catalog-card-body">
              <div className="catalog-title">{product.title}</div>
              <div className="catalog-desc">{product.description}</div>
              <div className="catalog-price">{product.price} ₸</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
