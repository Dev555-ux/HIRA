import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { authEnabled } from "@/lib/config";

export default async function Home() {
  if (!authEnabled) {
    redirect("/dashboard");
  }
  const { userId } = await auth();
  redirect(userId ? "/dashboard" : "/sign-in");
}
