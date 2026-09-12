import type { Metadata } from "next";
import { RecoveryForm } from "@/components/features/auth";

export const metadata: Metadata = { title: "Account recovery" };

export default function RecoverPage() {
  return <RecoveryForm />;
}
