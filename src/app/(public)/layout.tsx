import { HearthMarquee } from '@/components/hearth-marquee'

// Shared layout for the public, pre-login routes (/, /login, /register).
// Because Next keeps this layout mounted across client-side navigation between
// these pages, the photo marquee never remounts — the scroll animation runs
// continuously and the background doesn't flash/reload when moving between them.
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <HearthMarquee />
      <div className="relative z-10">{children}</div>
    </>
  )
}
