import { redirect } from 'next/navigation';
import { getSession } from '@/lib/auth';
import ChatApp from '@/components/ChatApp';

export default async function Home() {
  const user = await getSession();
  if (!user) redirect('/login');
  return <ChatApp user={user} />;
}
