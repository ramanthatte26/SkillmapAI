import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import { isTokenExpired } from '@/lib/utils';

export default async function RootPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get('skillmap_token')?.value;
  if (token && !isTokenExpired(token)) {
    redirect('/dashboard');
  } else {
    redirect('/login?logged_out=true');
  }
}

