// Matte (Samsung's framing border around the artwork) styles and colors, as the
// samsungtvws API expects them combined into one token, e.g. "modernthin_polar".
// "none" is a style on its own and takes no color.

export const MATTE_STYLES = [
  'none', 'modernthin', 'modern', 'modernwide', 'flexible',
  'shadowbox', 'panoramic', 'triptych', 'mix', 'squares',
] as const;

// "burgandy" is the spelling the API expects, not a typo here.
export const MATTE_COLORS = [
  'black', 'neutral', 'antique', 'warm', 'polar', 'sand', 'seafoam', 'sage',
  'burgandy', 'navy', 'apricot', 'byzantine', 'lavender', 'redorange', 'skyblue', 'turquoise',
] as const;

// Approximate on-screen colors, for the preview only. The TV renders its own.
export const MATTE_SWATCHES: Record<string, string> = {
  black: '#111111', neutral: '#d9d4cc', antique: '#cdbf9f', warm: '#e6d3b3',
  polar: '#f4f4f2', sand: '#d8c3a0', seafoam: '#9fc5b8', sage: '#a8b59a',
  burgandy: '#6d1f2c', navy: '#1f2f4f', apricot: '#f2b88c', byzantine: '#7a2f6a',
  lavender: '#b9a6d3', redorange: '#c8442a', skyblue: '#8ec5e8', turquoise: '#3fb6b0',
};

// How much of the frame the matte covers, as CSS padding. Percentages of padding are
// taken from the width on every side, so the border stays even all round; panoramic is
// the exception and is deliberately thinner top and bottom.
export const MATTE_PADDING: Record<string, string> = {
  none: '0',
  modernthin: '3%',
  modern: '6%',
  modernwide: '10%',
  flexible: '6%',
  shadowbox: '6%',
  panoramic: '4% 3%',
  triptych: '6%',
  mix: '6%',
  squares: '6%',
};

/** Combine a style and color into the API's single token. "none" takes no color. */
export function combineMatte(style: string, color: string): string {
  return !style || style === 'none' ? 'none' : `${style}_${color}`;
}

/** Split a stored token back into a style and color, for pre-filling a picker. */
export function splitMatte(value: string | null | undefined): { style: string; color: string } {
  if (!value || value === 'none') return { style: 'none', color: MATTE_COLORS[0] };
  const separator = value.indexOf('_');
  if (separator === -1) return { style: value, color: MATTE_COLORS[0] };
  return { style: value.slice(0, separator), color: value.slice(separator + 1) };
}
