import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { jwtVerify } from 'jose'

const secret = new TextEncoder().encode(
  process.env.SESSION_SECRET ?? 'dev-secret-change-in-production-32chars'
)

const PUBLIC_PATHS = ['/login', '/register', '/']

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith('/api/auth'))

  const token = request.cookies.get('meal-planner-session')?.value

  if (!isPublic && !token) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  if (token) {
    try {
      await jwtVerify(token, secret)
      if (pathname === '/login' || pathname === '/register') {
        return NextResponse.redirect(new URL('/planner', request.url))
      }
    } catch {
      if (!isPublic) {
        const response = NextResponse.redirect(new URL('/login', request.url))
        response.cookies.delete('meal-planner-session')
        return response
      }
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)'],
}
