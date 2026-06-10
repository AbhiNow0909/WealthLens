import { createServerSupabaseClient } from "@/lib/supabase-server";
import { redirect } from "next/navigation";
import FundDetailClient from "./FundDetailClient";

type Props = { params: Promise<{ id: string }> };

export default async function FundDetailPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return <FundDetailClient isin={id} />;
}
