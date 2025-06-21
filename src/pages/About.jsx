export default function About() {
  return (
    <section className="form-block" style={{
      maxWidth: 800,
      margin: "48px auto 0",
      background: "#fff",
      boxShadow: "0 4px 24px 0 rgba(233,30,99,0.09)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center"
    }}>
      <img
        src="https://images.unsplash.com/photo-1506744038136-46273834b3fb?fit=crop&w=400&q=80"
        alt="Основатель Amor Flowers"
        style={{
          width: 120,
          height: 120,
          objectFit: "cover",
          borderRadius: "50%",
          boxShadow: "0 2px 24px 0 rgba(233,30,99,0.16)",
          marginBottom: 22,
          border: "4px solid #ef5da8"
        }}
      />
      <h1 style={{
        fontSize: "2rem",
        fontWeight: 900,
        color: "#ef5da8",
        marginBottom: 10,
        textAlign: "center"
      }}>
        О нас
      </h1>
      <div style={{
        fontSize: 18,
        color: "#4e324e",
        textAlign: "center",
        maxWidth: 650,
        marginBottom: 24
      }}>
        <span style={{color: "#ef5da8", fontWeight: 700}}>Amor Flowers</span> — это современная цветочная студия, где каждый букет создаётся с душой и особым вниманием к деталям.
        <br /><br />
        Основатель студии — <b style={{color: "#c42f76"}}>Татьяна</b>, профессиональный флорист с 10-летним опытом в премиум-сегменте, вдохновляется красотой природы и европейскими трендами.
        <br /><br />
        Мы верим, что цветы могут говорить больше тысячи слов. Наши клиенты доверяют нам самые важные события: дни рождения, свадьбы, юбилеи, признания и просто тёплые моменты.
        <br /><br />
        <span style={{
          display: "inline-block",
          background: "#ffe5f1",
          color: "#ef5da8",
          borderRadius: 12,
          padding: "5px 22px",
          fontWeight: 700,
          margin: "18px 0 0"
        }}>
          Мы всегда рядом, чтобы ваши чувства выглядели идеально!
        </span>
      </div>
    </section>
  );
}
