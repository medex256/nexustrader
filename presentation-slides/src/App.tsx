import { slides } from "./slides";

export function App() {
  return (
    <main className="deck-shell">
      <header className="deck-header">
        <div>
          <p className="eyebrow">NexusTrader Presentation Prototype</p>
          <h1>Minimalist HTML Slides</h1>
          <p className="deck-summary">
            Separate from the live frontend. Built for clean visual review first,
            then later export to PNG or PPTX.
          </p>
        </div>
        <div className="deck-meta">
          <span>{slides.length} slides</span>
          <span>16:9 layout</span>
          <span>light theme</span>
        </div>
      </header>

      <section className="deck-grid">
        {slides.map((slide) => (
          <article key={slide.id} className="slide-frame">
            <div className="slide-meta">
              <span>Slide {slide.number}</span>
              <span>{slide.tag}</span>
            </div>
            <div className="slide-canvas">{slide.content}</div>
          </article>
        ))}
      </section>
    </main>
  );
}