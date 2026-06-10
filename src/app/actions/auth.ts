'use server'

import bcrypt from 'bcryptjs'
import { redirect } from 'next/navigation'
import { db } from '@/lib/db'
import { createSession, deleteSession } from '@/lib/session'

export async function signup(_prevState: unknown, formData: FormData) {
  const name = formData.get('name') as string
  const email = formData.get('email') as string
  const password = formData.get('password') as string

  if (!email || !password) return { error: 'Email and password are required' }
  if (password.length < 8) return { error: 'Password must be at least 8 characters' }

  const existing = await db.user.findUnique({ where: { email } })
  if (existing) return { error: 'An account with this email already exists' }

  const passwordHash = await bcrypt.hash(password, 12)
  const user = await db.user.create({
    data: { email, name: name || null, passwordHash },
  })

  await createSession({ userId: user.id, email: user.email, name: user.name })
  redirect('/planner')
}

export async function login(_prevState: unknown, formData: FormData) {
  const email = formData.get('email') as string
  const password = formData.get('password') as string

  if (!email || !password) return { error: 'Email and password are required' }

  const user = await db.user.findUnique({ where: { email } })
  if (!user) return { error: 'Invalid email or password' }

  const valid = await bcrypt.compare(password, user.passwordHash)
  if (!valid) return { error: 'Invalid email or password' }

  await createSession({ userId: user.id, email: user.email, name: user.name })
  redirect('/planner')
}

export async function logout() {
  await deleteSession()
  redirect('/login')
}
