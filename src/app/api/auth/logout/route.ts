import { NextResponse } from 'next/server'

// Clears the session cookie and sends the user to /login. Used both by an
// explicit sign-out and as the redirect target when a session points at a user
// that no longer exists (e.g. switching databases, or a deleted account) —
// cookies can't be modified during a Server Component render, but they can here.
export function GET(request: Request) {
  const res = NextResponse.redirect(new URL('/login', request.url))
  res.cookies.delete('meal-planner-session')
  return res
}
