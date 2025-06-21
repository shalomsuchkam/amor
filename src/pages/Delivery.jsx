export default function Delivery() {
  return (
    <section className="form-block" style={{
      maxWidth: 750,
      margin: "48px auto 0",
      background: "#fff",
      boxShadow: "0 4px 24px 0 rgba(233,30,99,0.09)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center"
    }}>
      <h1 style={{
        fontSize: "2rem",
        fontWeight: 900,
        color: "#ef5da8",
        marginBottom: 16,
        textAlign: "center"
      }}>
        🚗 Доставка
      </h1>
      <div style={{
        fontSize: 17,
        color: "#4e324e",
        textAlign: "center",
        maxWidth: 600,
        marginBottom: 22
      }}>
        Мы бережно доставляем цветы <b>по всему Алматы</b> и ближайшим районам.
        <br /><br />
        Наши курьеры всегда вежливы, аккуратны и вовремя привезут ваш заказ — будь то раннее утро, обеденный перерыв или поздний вечер.
        <br /><br />
        <span style={{
          display: "inline-block",
          background: "#ffe5f1",
          color: "#ef5da8",
          borderRadius: 10,
          padding: "6px 16px",
          fontWeight: 700,
          margin: "10px 0"
        }}>
          Адрес магазина:{" "}
          <a
            href="https://2gis.kz/almaty/firm/70000001081800821"
            target="_blank"
            rel="noopener noreferrer"
            style={{color:"#c42f76", textDecoration:"underline"}}
          >
            Алматы, ул. Алиби Жангельдина, 12
          </a>
        </span>
        <br />
        <span style={{fontWeight: 700, color: "#ef5da8"}}>
          Звонки и WhatsApp:{" "}
          <a
            href="https://wa.me/77714554477"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "#24cc63",
              background: "#e9fef1",
              borderRadius: 8,
              padding: "2px 11px",
              textDecoration: "none"
            }}>
            +7&nbsp;771&nbsp;455&nbsp;4477
          </a>
        </span>
        <br /><br />
        <span style={{
          display: "inline-block",
          color: "#ef5da8",
          background: "#fff0f7",
          fontWeight: 700,
          borderRadius: 10,
          padding: "8px 18px",
          fontSize: "1rem"
        }}>
          <span role="img" aria-label="timer">⏰</span> Ближайшая отправка: <b id="delivery-timer">через 10 минут</b>
        </span>
        <br /><br />
        <span style={{fontSize: 15, color:"#987697"}}>
          Любые вопросы — пишите в WhatsApp, мы онлайн 24/7 🌸
        </span>
      </div>
      <a
        href="https://wa.me/77714554477"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: "inline-flex",
          alignItems: "center",
          marginTop: 12,
          background: "#25d366",
          color: "#fff",
          borderRadius: 23,
          padding: "11px 28px",
          fontWeight: 700,
          fontSize: "1.15rem",
          textDecoration: "none",
          boxShadow: "0 1px 16px 0 #25d36644"
        }}
      >
        <span style={{fontSize: 23, marginRight: 10}}>💬</span>
        WhatsApp
      </a>
    </section>
  );
}
