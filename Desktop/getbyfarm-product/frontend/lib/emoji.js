const KEYWORDS = [
  [/tomato/i, "🍅"],
  [/onion/i, "🧅"],
  [/rice|grain/i, "🌾"],
  [/chicken|poultry/i, "🍗"],
  [/beef|meat/i, "🥩"],
  [/fish/i, "🐟"],
  [/egg/i, "🥚"],
  [/oil/i, "🛢️"],
  [/detergent|clean/i, "🧴"],
  [/water|juice|drink|beverage/i, "🧃"],
  [/bag|pack/i, "📦"],
];

export function guessEmoji(productName) {
  const match = KEYWORDS.find(([re]) => re.test(productName));
  return match ? match[1] : "📦";
}
