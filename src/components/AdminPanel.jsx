import React, { useState } from "react";
import AddProductBlock from "./AddProductBlock";
import EditProductBlock from "./EditProductBlock";
import "./AdminPanel.css";

export default function AdminPanel() {
  const [active, setActive] = useState("add");

  return (
    <div className="admin-panel-root">
      <div className="admin-panel-header">
        <button
          className={`admin-panel-tab${active === "add" ? " active" : ""}`}
          onClick={() => setActive("add")}
        >
          <span className="admin-panel-tab-icon">➕</span> Добавить букет
        </button>
        <button
          className={`admin-panel-tab${active === "edit" ? " active" : ""}`}
          onClick={() => setActive("edit")}
        >
          <span className="admin-panel-tab-icon">📝</span> Редактировать букеты
        </button>
      </div>
      <div className="admin-panel-content">
        {active === "add" ? <AddProductBlock /> : <EditProductBlock />}
      </div>
    </div>
  );
}
