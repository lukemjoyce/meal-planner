import Link from 'next/link'
import { buttonVariants } from '@/components/ui/button'

export default function Home() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <div className="relative z-10 max-w-2xl py-20">
        <div className="mx-auto rounded-4xl bg-background/70 px-6 py-10 shadow-xl ring-1 ring-border/50 backdrop-blur-md sm:px-10">
          <div className="bg-primary mx-auto mb-6 grid size-16 place-content-center rounded-2xl text-3xl shadow-lg shadow-primary/25">
            🛒
          </div>
          <h1 className="mb-4 text-4xl font-extrabold tracking-tight sm:text-6xl">
            <span className="text-primary">Smart</span> Meal Planning
          </h1>
          <p className="mx-auto mb-2 max-w-xl text-lg text-muted-foreground">
            Plan your week&apos;s meals with AI. Get a grocery list that reuses ingredients across
            meals, matches real package sizes, and keeps you on budget.
          </p>
          <p className="mx-auto mb-8 max-w-lg text-sm text-muted-foreground/80">
            One cilantro bunch across three meals. Sour cream split perfectly between tacos and soup.
            Zero waste, maximum flavor.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Link href="/register" className={buttonVariants({ size: 'lg' })}>
              Get Started Free
            </Link>
            <Link href="/login" className={buttonVariants({ variant: 'outline', size: 'lg' })}>
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </main>
  )
}
