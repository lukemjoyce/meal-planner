import { getProfile } from '@/app/actions/profile'
import { ProfileClient } from '@/components/profile-client'

export default async function ProfilePage() {
  const profile = await getProfile()
  return <ProfileClient profile={profile} />
}
