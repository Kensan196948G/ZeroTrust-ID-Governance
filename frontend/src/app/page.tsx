import { redirect } from 'next/navigation';

// ルートは /dashboard にリダイレクト
export default function RootPage() {
  redirect('/dashboard');
}
