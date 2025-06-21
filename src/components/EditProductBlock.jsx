import React, { useEffect, useState } from "react";
import { supabase } from "../supabaseClient";
import COLORS from "../data/colors";
import FLOWER_TYPES from "../data/flowers";
import OCCASIONS from "../data/occasions";
import "./EditProductBlock.css";

export default function EditProductBlock() {
  const [products, setProducts] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  // Загрузка всех товаров
  useEffect(() => {
    fetchProducts();
  }, []);

  async function fetchProducts() {
    setLoading(true);
    const { data, error } = await supabase.from("products").select("*").order("id", { ascending: false });
    setProducts(data || []);
    setLoading(false);
    if (error) setMsg("Ошибка загрузки товаров: " + error.message);
  }

  function handleEditInit(product) {
    setEditingId(product.id);
    setEditData({
      ...product,
      colors: Array.isArray(product.colors)
        ? product.colors
        : product.colors
        ? JSON.parse(product.colors)
        : [],
      types: Array.isArray(product.types)
        ? product.types
        : product.types
        ? JSON.parse(product.types)
        : [],
      occasions: Array.isArray(product.occasions)
        ? product.occasions
        : product.occasions
        ? JSON.parse(product.occasions)
        : [],
    });
  }

  function handleEditChange(field, value) {
    setEditData((prev) => ({ ...prev, [field]: value }));
  }

  function toggleEditArray(field, value) {
    setEditData((prev) => {
      const arr = Array.isArray(prev[field]) ? prev[field] : [];
      return {
        ...prev,
        [field]: arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value],
      };
    });
  }

  async function handleEditSave() {
    setLoading(true);
    setMsg("");
    try {
      const { error } = await supabase
        .from("products")
        .update({
          title: editData.title,
          image: editData.image,
          price: Number(editData.price),
          colors: JSON.stringify(editData.colors),
          types: JSON.stringify(editData.types),
          occasions: JSON.stringify(editData.occasions),
        })
        .eq("id", editingId);

      if (error) throw error;
      setMsg("✔️ Успешно обновлено");
      setEditingId(null);
      setEditData({});
      fetchProducts();
    } catch (e) {
      setMsg("❗ Ошибка: " + e.message);
    }
    setLoading(false);
  }

  async function handleDelete(id) {
    if (!window.confirm("Удалить этот букет?")) return;
    setLoading(true);
    setMsg("");
    await supabase.from("products").delete().eq("id", id);
    fetchProducts();
    setLoading(false);
  }

  return (
    <div className="edit-block">
      <h2 className="edit-block-title">Изменить и удалить букеты</h2>
      {msg && <div className="edit-block-msg">{msg}</div>}
      <div className="edit-block-list">
        {loading ? (
          <div className="edit-block-loading">Загрузка...</div>
        ) : products.length === 0 ? (
          <div className="edit-block-empty">Нет букетов</div>
        ) : (
          products.map((product) =>
            editingId === product.id ? (
              <div key={product.id} className="edit-block-item edit-block-item-editing">
                <input
                  value={editData.title || ""}
                  onChange={(e) => handleEditChange("title", e.target.value)}
                  placeholder="Название"
                />
                <input
                  value={editData.image || ""}
                  onChange={(e) => handleEditChange("image", e.target.value)}
                  placeholder="Ссылка на изображение"
                />
                {editData.image ? (
                  <img src={editData.image} alt="preview" className="edit-block-preview" />
                ) : (
                  <div className="edit-block-preview edit-block-preview-empty">Нет изображения</div>
                )}
                <input
                  type="number"
                  value={editData.price || ""}
                  onChange={(e) => handleEditChange("price", e.target.value)}
                  placeholder="Цена"
                />
                <div className="edit-block-checkboxes">
                  <b>Цвета:</b>
                  {COLORS.map((c) => (
                    <label key={c.name}>
                      <input
                        type="checkbox"
                        checked={editData.colors?.includes(c.name)}
                        onChange={() => toggleEditArray("colors", c.name)}
                      />
                      <span
                        style={{
                          background: c.code,
                          display: "inline-block",
                          width: 16,
                          height: 16,
                          borderRadius: "50%",
                          marginRight: 6,
                          verticalAlign: "middle",
                          border: "1.5px solid #e2e2e2",
                        }}
                      ></span>
                      {c.name}
                    </label>
                  ))}
                </div>
                <div className="edit-block-checkboxes">
                  <b>Тип цветов:</b>
                  {FLOWER_TYPES.map((t) => (
                    <label key={t}>
                      <input
                        type="checkbox"
                        checked={editData.types?.includes(t)}
                        onChange={() => toggleEditArray("types", t)}
                      />
                      {t}
                    </label>
                  ))}
                </div>
                <div className="edit-block-checkboxes edit-block-occasions">
                  <b>Поводы:</b>
                  {OCCASIONS.map((group) => (
                    <div key={group.group} className="occasion-group">
                      <details>
                        <summary>{group.group}</summary>
                        <div>
                          {group.items.map((item) => (
                            <label key={item}>
                              <input
                                type="checkbox"
                                checked={editData.occasions?.includes(item)}
                                onChange={() => toggleEditArray("occasions", item)}
                              />
                              {item}
                            </label>
                          ))}
                        </div>
                      </details>
                    </div>
                  ))}
                </div>
                <div className="edit-block-actions">
                  <button className="edit-block-btn" onClick={handleEditSave} disabled={loading}>
                    Сохранить
                  </button>
                  <button className="edit-block-btn edit-block-btn-cancel" onClick={() => setEditingId(null)} type="button">
                    Отмена
                  </button>
                </div>
              </div>
            ) : (
              <div key={product.id} className="edit-block-item">
                <div className="edit-block-info">
                  <img src={product.image} alt="" className="edit-block-thumb" />
                  <div>
                    <div className="edit-block-title">{product.title}</div>
                    <div className="edit-block-price">{product.price} ₸</div>
                  </div>
                </div>
                <div className="edit-block-actions">
                  <button className="edit-block-btn" onClick={() => handleEditInit(product)}>
                    ✏️ Редактировать
                  </button>
                  <button className="edit-block-btn edit-block-btn-delete" onClick={() => handleDelete(product.id)}>
                    🗑️ Удалить
                  </button>
                </div>
              </div>
            )
          )
        )}
      </div>
    </div>
  );
}
