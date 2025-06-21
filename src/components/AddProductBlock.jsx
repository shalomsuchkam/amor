import React, { useState } from "react";
import { supabase } from "../supabaseClient";
import COLORS from "../data/colors";
import FLOWER_TYPES from "../data/flowers";
import OCCASIONS from "../data/occasions";
import "./AddProductBlock.css";

export default function AddProductBlock() {
  const [title, setTitle] = useState("");
  const [image, setImage] = useState("");
  const [price, setPrice] = useState("");
  const [colors, setColors] = useState([]);
  const [types, setTypes] = useState([]);
  const [occasions, setOccasions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const handleColor = (color) => {
    setColors((prev) =>
      prev.includes(color)
        ? prev.filter((c) => c !== color)
        : [...prev, color]
    );
  };

  const handleType = (type) => {
    setTypes((prev) =>
      prev.includes(type)
        ? prev.filter((t) => t !== type)
        : [...prev, type]
    );
  };

  const handleOccasion = (occasion) => {
    setOccasions((prev) =>
      prev.includes(occasion)
        ? prev.filter((o) => o !== occasion)
        : [...prev, occasion]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg("");
    try {
      const { error } = await supabase.from("products").insert([
        {
          title,
          image,
          price: Number(price),
          colors: JSON.stringify(colors),
          types: JSON.stringify(types),
          occasions: JSON.stringify(occasions),
        },
      ]);
      if (error) throw error;
      setTitle("");
      setImage("");
      setPrice("");
      setColors([]);
      setTypes([]);
      setOccasions([]);
      setMsg("✔️ Букет успешно добавлен!");
    } catch (e) {
      setMsg("❗ Ошибка добавления: " + e.message);
    }
    setLoading(false);
  };

  return (
    <form className="add-block" onSubmit={handleSubmit}>
      <div className="add-block-row">
        <div className="add-block-group">
          <label>Название:</label>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Название букета"
            required
          />
        </div>
        <div className="add-block-group">
          <label>Ссылка на изображение:</label>
          <input
            value={image}
            onChange={e => setImage(e.target.value)}
            placeholder="https://..."
            required
          />
        </div>
        {image ? (
          <div className="add-block-preview">
            <img src={image} alt="preview" />
          </div>
        ) : (
          <div className="add-block-preview add-block-preview-empty">Нет изображения</div>
        )}
      </div>

      <div className="add-block-group">
        <label>Цена:</label>
        <input
          type="number"
          value={price}
          onChange={e => setPrice(e.target.value)}
          placeholder="Цена"
          required
        />
      </div>

      <div className="add-block-row">
        <div className="add-block-group">
          <label>Цвета:</label>
          <div className="add-block-checkboxes">
            {COLORS.map(color => (
              <label key={color.name}>
                <input
                  type="checkbox"
                  checked={colors.includes(color.name)}
                  onChange={() => handleColor(color.name)}
                />
                <span style={{
                  background: color.code,
                  display: "inline-block",
                  width: 16, height: 16,
                  borderRadius: "50%",
                  marginRight: 6, verticalAlign: "middle",
                  border: "1.5px solid #e2e2e2"
                }}></span>
                {color.name}
              </label>
            ))}
          </div>
        </div>
        <div className="add-block-group">
          <label>Тип цветов:</label>
          <div className="add-block-checkboxes">
            {FLOWER_TYPES.map(type => (
              <label key={type}>
                <input
                  type="checkbox"
                  checked={types.includes(type)}
                  onChange={() => handleType(type)}
                />
                {type}
              </label>
            ))}
          </div>
        </div>
        <div className="add-block-group">
          <label>Поводы:</label>
          <div className="add-block-checkboxes add-block-occasions">
            {OCCASIONS.map(group => (
              <div key={group.group} className="occasion-group">
                <details>
                  <summary>{group.group}</summary>
                  <div>
                    {group.items.map(item => (
                      <label key={item}>
                        <input
                          type="checkbox"
                          checked={occasions.includes(item)}
                          onChange={() => handleOccasion(item)}
                        />
                        {item}
                      </label>
                    ))}
                  </div>
                </details>
              </div>
            ))}
          </div>
        </div>
      </div>
      <button type="submit" className="add-block-btn" disabled={loading}>
        {loading ? "Добавление..." : "Добавить букет"}
      </button>
      {msg && <div className="add-block-msg">{msg}</div>}
    </form>
  );
}
