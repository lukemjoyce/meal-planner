// Decorative full-bleed background for the landing page: rows of photos that
// scroll horizontally, alternating direction per row, in a staggered brick
// layout. Pure CSS animation (see .hearth-track in globals.css) — no client JS.
// Tiles use background-image divs (decorative, so no <img>/alt needed).

const PHOTO_COUNT = 15
const PHOTOS = Array.from(
  { length: PHOTO_COUNT },
  (_, i) => `/hearth/photo-${String(i + 1).padStart(2, '0')}.webp`
)

const ROWS = 6

export function HearthMarquee() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
      <div className="flex h-full min-h-screen flex-col">
        {Array.from({ length: ROWS }).map((_, row) => {
          const reverse = row % 2 === 1
          // Rotate the starting photo per row so tiles never line up column-to-column.
          const offset = (row * 5) % PHOTO_COUNT
          const rowPhotos = [...PHOTOS.slice(offset), ...PHOTOS.slice(0, offset)]
          // Duplicate the set so translateX(-50%) loops seamlessly.
          const track = [...rowPhotos, ...rowPhotos]
          return (
            <div key={row} className="relative flex-1 overflow-hidden">
              <div
                className="hearth-track flex h-full w-max"
                style={{
                  // Slow, slightly varied per row so they drift out of sync.
                  animationDuration: `${200 + (row % 3) * 100}s`,
                  animationDirection: reverse ? 'reverse' : 'normal',
                  // Half-tile horizontal stagger → brick pattern.
                  marginLeft: reverse ? '-8vw' : '0',
                }}
              >
                {track.map((src, idx) => (
                  <div key={idx} className="h-full w-[17vw] min-w-[150px] shrink-0 p-1">
                    <div
                      className="h-full w-full rounded-lg bg-cover bg-center shadow-sm"
                      style={{ backgroundImage: `url(${src})` }}
                    />
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
      {/* Soft scrim to unify the photos and keep foreground text readable. */}
      <div className="absolute inset-0 bg-background/55" />
    </div>
  )
}
