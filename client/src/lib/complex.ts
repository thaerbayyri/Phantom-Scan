// Complex number utilities for signal processing

export interface Complex {
  re: number;
  im: number;
}

export function complex(re: number, im: number = 0): Complex {
  return { re, im };
}

export function add(a: Complex, b: Complex): Complex {
  return { re: a.re + b.re, im: a.im + b.im };
}

export function sub(a: Complex, b: Complex): Complex {
  return { re: a.re - b.re, im: a.im - b.im };
}

export function mul(a: Complex, b: Complex): Complex {
  return {
    re: a.re * b.re - a.im * b.im,
    im: a.re * b.im + a.im * b.re,
  };
}

export function div(a: Complex, b: Complex): Complex {
  const denom = b.re * b.re + b.im * b.im;
  if (denom < 1e-10) {
    return { re: 0, im: 0 };
  }
  return {
    re: (a.re * b.re + a.im * b.im) / denom,
    im: (a.im * b.re - a.re * b.im) / denom,
  };
}

export function conj(a: Complex): Complex {
  return { re: a.re, im: -a.im };
}

export function magnitude(a: Complex): number {
  return Math.sqrt(a.re * a.re + a.im * a.im);
}

export function phase(a: Complex): number {
  return Math.atan2(a.im, a.re);
}

export function scale(a: Complex, s: number): Complex {
  return { re: a.re * s, im: a.im * s };
}

export function negate(a: Complex): Complex {
  return { re: -a.re, im: -a.im };
}

export function fromPolar(mag: number, angle: number): Complex {
  return {
    re: mag * Math.cos(angle),
    im: mag * Math.sin(angle),
  };
}

// Calculate precoding ratio: p = -h1/h2
export function calculatePrecodingRatio(h1: Complex, h2: Complex): Complex {
  return negate(div(h1, h2));
}
