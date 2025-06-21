export default function Contacts() {
  return (
    <section className="form-block" style={{
      maxWidth: 600,
      margin: "54px auto 0",
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
        marginBottom: 18,
        textAlign: "center"
      }}>
        Контакты
      </h1>
      <div style={{fontSize: 17, color: "#4e324e", textAlign: "center", maxWidth: 430, marginBottom: 18}}>
        Всегда на связи — звоните, пишите или приезжайте в гости!
        <br /><br />
        <span style={{fontWeight: 700, color: "#ef5da8"}}>WhatsApp/телефон:&nbsp;</span>
        <a
          href="https://wa.me/77714554477"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: "#24cc63",
            background: "#e9fef1",
            borderRadius: 8,
            padding: "2px 13px",
            fontWeight: 700,
            textDecoration: "none"
          }}>
          +7&nbsp;771&nbsp;455&nbsp;4477
        </a>
        <br /><br />
        <span style={{fontWeight: 700, color: "#ef5da8"}}>Instagram:&nbsp;</span>
        <a
          href="https://www.instagram.com/amor_flowers_almaty/"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: "#c42f76",
            background: "#ffe5f1",
            borderRadius: 8,
            padding: "2px 13px",
            fontWeight: 700,
            textDecoration: "none"
          }}>
          @amor_flowers_almaty
        </a>
        <br /><br />
        <span style={{color: "#9a86aa", fontSize: 15}}>Адрес: Алматы, ул. Алиби Жангельдина, 12</span>
      </div>
      <a
        href="https://wa.me/77714554477"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: "inline-flex",
          alignItems: "center",
          marginTop: 8,
          background: "#25d366",
          color: "#fff",
          borderRadius: 22,
          padding: "12px 30px",
          fontWeight: 700,
          fontSize: "1.12rem",
          textDecoration: "none",
          boxShadow: "0 1px 16px 0 #25d36644"
        }}
      >
        <span style={{fontSize: 22, marginRight: 10}}>💬</span>
        Написать в WhatsApp
      </a>
    </section>
  );
}
