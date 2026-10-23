/** Small brand motifs that echo the logo's green–orange–green rhythm ("GET · BY · FARM"). */

/** A thin three-part bar: green, orange, green: the wordmark's colour sequence as a divider. */
export function TriBar({ className = "h-1" }) {
  return (
    <div className={`flex w-full overflow-hidden ${className}`} aria-hidden>
      <span className="basis-[38%] bg-leaf-600" />
      <span className="basis-[24%] bg-ember-500" />
      <span className="basis-[38%] bg-leaf-600" />
    </div>
  );
}

/** "GetbyFarm" coloured like the logo: Get (green) by (orange) Farm (green). `onDark` lightens the green. */
export function BrandWord({ onDark = false }) {
  const green = onDark ? "text-paper" : "text-leaf-600";
  return (
    <span className="whitespace-nowrap">
      <span className={green}>Get</span>
      <span className={onDark ? "text-ember-500" : "text-ember-500"}>by</span>
      <span className={green}>Farm</span>
    </span>
  );
}
