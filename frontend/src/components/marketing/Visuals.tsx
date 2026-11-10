import type { CSSProperties } from 'react';

export function CandleVisual() {
  return (
    <div className="oneb-candle-scene" aria-label="Candlesticks metálicos em uma superfície escura">
      {[28, 42, 58, 74, 88, 104].map((height, index) => (
        <span key={height} className="oneb-candle" style={{ height: `${height * 2}px`, '--i': index } as CSSProperties}>
          <i />
        </span>
      ))}
    </div>
  );
}

export function CommunityMockup() {
  return (
    <div className="oneb-community-phone" aria-label="Prévia da Comunidade OneB">
      <header>
        <span>←</span>
        <strong>Comunidade OneB</strong>
        <span>⋮</span>
      </header>
      {[
        ['Lucas O.', 'Alguém operando 13X no Nasdaq hoje?'],
        ['Trader Alfa', 'Excelente leitura pessoal. Gestão de risco sempre em primeiro lugar.'],
        ['OneB Mentor', 'Setup interessante no S&P. Aguardem confirmação antes da entrada.'],
      ].map(([name, text]) => (
        <div key={text} className="oneb-post">
          <b>{name}</b>
          <p>{text}</p>
        </div>
      ))}
      <div className="oneb-mini-chart" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
