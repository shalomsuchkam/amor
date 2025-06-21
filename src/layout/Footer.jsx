import React from "react";
import "./Footer.css";

export default function Footer() {
  return (
    <footer className="amor-footer">
      <div className="footer-main">
        <div className="footer-brand">
          <span className="footer-logo">💐</span>
          <span className="footer-title">Amor Flowers</span>
          <span className="footer-slogan">Делаем ваш день ярче!</span>
        </div>
        <div className="footer-links">
          <a
            href="https://instagram.com/amor_flowers_almaty"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-social"
            aria-label="Instagram"
          >
            {/* Instagram SVG — мини круглый стиль */}
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="16" fill="#F03078"/>
              <g>
                <rect x="9" y="9" width="14" height="14" rx="4" stroke="#fff" strokeWidth="2"/>
                <circle cx="16" cy="16" r="3.5" stroke="#fff" strokeWidth="2"/>
                <circle cx="21.1" cy="10.9" r="1" fill="#fff"/>
              </g>
            </svg>
          </a>
          <a
            href="https://wa.me/77714554477"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-social"
            aria-label="WhatsApp"
          >
            {/* WhatsApp SVG — мини круглый стиль */}
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="16" fill="#25D366"/>
              <g>
                <path d="M22.2 17.5c-.3-.1-1.7-.8-1.9-.9-.2-.1-.4-.1-.5.1s-.6.8-.8 1c-.1.1-.2.1-.4.1-.3-.1-1.2-.5-2.3-1.5s-1.6-2-1.8-2.3c-.2-.3 0-.4.1-.5.1-.1.2-.3.3-.4.1-.1.2-.2.3-.3.1-.1.1-.2.2-.3.1-.1.1-.2.2-.3.1-.1 0-.3-.1-.4-.1-.1-.6-1.4-.8-1.8-.2-.4-.4-.4-.5-.4h-.5c-.2 0-.5.1-.8.4-.3.3-1 1-.9 2.4s1.1 2.9 1.2 3.1c.2.2 1.9 3.2 4.6 4.3.6.2 1.1.4 1.5.5.6.1 1.2.1 1.6.1.5-.1 1.7-.7 2-1.3.2-.6.2-1.2.1-1.3-.1-.2-.3-.2-.6-.4z" fill="#fff"/>
              </g>
            </svg>
          </a>
        </div>
        <div className="footer-menu">
          <a href="/catalog">Каталог</a>
          <a href="/about">О нас</a>
          <a href="/delivery">Доставка</a>
          <a href="/contacts">Контакты</a>
        </div>
        <div className="footer-contacts">
          <span>г. Алматы, Казахстан</span>
          <a href="tel:+77714554477">+7 771 455 44 77</a>
          <a href="https://wa.me/77714554477" target="_blank" rel="noopener noreferrer">
            WhatsApp: +7 771 455 44 77
          </a>
          <a href="https://instagram.com/amor_flowers_almaty" target="_blank" rel="noopener noreferrer">
            Instagram: @amor_flowers_almaty
          </a>
        </div>
      </div>
      <div className="footer-copy">
        © {new Date().getFullYear()} Amor Flowers — Цветы с любовью 💕
      </div>
    </footer>
  );
}
